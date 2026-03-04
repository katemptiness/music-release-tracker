#!/usr/bin/env python3
"""Standalone script to check for new music releases and send Telegram notifications.

Usage:
    python notify.py           # Run check and notify via Telegram
    python notify.py --setup   # Interactive setup for Telegram bot
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

import db
import musicbrainz

CONFIG_PATH = Path(__file__).parent / "telegram_config.json"
TELEGRAM_API = "https://api.telegram.org/bot{token}"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("Error: telegram_config.json not found. Run 'python notify.py --setup' first.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Config saved to {CONFIG_PATH}")


async def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        })
        if resp.status_code == 200:
            return True
        print(f"Telegram API error: {resp.status_code} {resp.text}")
        return False


async def get_updates(token: str) -> dict:
    url = f"{TELEGRAM_API.format(token=token)}/getUpdates"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def run_check() -> list[dict]:
    """Check all artists for new releases. Returns a summary list."""
    db.init_db()
    artists = db.get_all_artists()

    if not artists:
        print("No artists tracked.")
        return []

    summary = []
    for artist in artists:
        try:
            releases = await musicbrainz.get_artist_releases(artist["mbid"])
        except Exception as e:
            print(f"Error checking {artist['name']}: {e}")
            continue

        new_titles = []
        for rel in releases:
            inserted = db.add_release(
                mbid=rel["mbid"],
                artist_id=artist["id"],
                title=rel["title"],
                release_type=rel["type"],
                release_date=rel["date"],
                notified=0,
            )
            if inserted:
                new_titles.append({
                    "title": rel["title"],
                    "type": rel["type"],
                    "date": rel["date"],
                })

        if new_titles:
            summary.append({"artist": artist["name"], "releases": new_titles})

    return summary


def format_message(summary: list[dict]) -> str:
    total_releases = sum(len(s["releases"]) for s in summary)
    total_artists = len(summary)

    lines = ["\U0001f3b5 <b>New releases found!</b>\n"]
    for entry in summary:
        lines.append(f"<b>{entry['artist']}</b>:")
        for rel in entry["releases"]:
            date_part = f" \u2014 {rel['date']}" if rel["date"] else ""
            lines.append(f"  \u2022 {rel['title']} ({rel['type']}){date_part}")
        lines.append("")

    lines.append(f"Found {total_releases} new release(s) across {total_artists} artist(s).")
    return "\n".join(lines)


def check_release_day() -> list[dict]:
    """Check for releases that come out today."""
    db.init_db()
    return db.get_releases_due_today()


def format_release_day_message(releases: list[dict]) -> str:
    lines = ["\U0001f4c5 <b>Out today — go listen!</b>\n"]
    for r in releases:
        lines.append(f"  \u2022 <b>{r['artist_name']}</b> \u2014 {r['title']} ({r['release_type']})")
    lines.append(f"\n{len(releases)} release(s) out today.")
    return "\n".join(lines)


async def setup():
    """Interactive setup for Telegram bot."""
    print("=" * 50)
    print("  Telegram Bot Setup")
    print("=" * 50)
    print()
    print("Step 1: Create a Telegram bot")
    print("  1. Open Telegram and search for @BotFather")
    print("  2. Send /newbot and follow the instructions")
    print("  3. Copy the bot token BotFather gives you")
    print()

    token = input("Paste your bot token here: ").strip()
    if not token:
        print("No token provided. Aborting.")
        return

    print()
    print("Step 2: Get your chat ID")
    print("  1. Open Telegram and find your new bot")
    print("  2. Send it any message (e.g. 'hello')")
    print()
    input("Press Enter after you've sent a message to your bot...")

    data = await get_updates(token)
    results = data.get("result", [])
    if not results:
        print("No messages found. Make sure you sent a message to your bot and try again.")
        return

    chat_id = str(results[-1]["message"]["chat"]["id"])
    print(f"  Found chat ID: {chat_id}")
    print()

    print("Step 3: Sending test message...")
    success = await send_telegram_message(token, chat_id, "\u2705 Music Release Tracker connected!")
    if not success:
        print("Failed to send test message. Check your token and try again.")
        return

    print("  Test message sent! Check your Telegram.")
    print()

    save_config({"bot_token": token, "chat_id": chat_id})

    project_dir = Path(__file__).parent.resolve()
    print()
    print("Step 4: Set up weekly cron job (optional)")
    print("  Run 'crontab -e' and add this line:")
    print()
    print(f"  0 10 * * 5 cd {project_dir} && {sys.executable} notify.py >> notify.log 2>&1")
    print()
    print("  This runs every Friday at 10:00 AM.")
    print()
    print("Setup complete!")


async def main():
    if "--setup" in sys.argv:
        await setup()
        return

    config = load_config()
    token = config["bot_token"]
    chat_id = config["chat_id"]

    print(f"Checking for new releases...")
    summary = await run_check()

    if not summary:
        print("No new releases found.")
    else:
        message = format_message(summary)
        print(message)
        print()
        success = await send_telegram_message(token, chat_id, message)
        if success:
            print("Telegram notification sent!")
        else:
            print("Failed to send Telegram notification.")

    # Release-day notifications
    due_today = check_release_day()
    if due_today:
        day_message = format_release_day_message(due_today)
        print(day_message)
        print()
        success = await send_telegram_message(token, chat_id, day_message)
        if success:
            for r in due_today:
                db.mark_release_day_notified(r["id"])
            print("Release-day notification sent!")
        else:
            print("Failed to send release-day notification.")
    else:
        print("No releases due today.")


if __name__ == "__main__":
    asyncio.run(main())
