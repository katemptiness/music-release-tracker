# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
pip install -r requirements.txt
python app.py
```

Starts a FastAPI server on `http://127.0.0.1:8080` and auto-opens the browser. No tests or linter are configured yet.

## Architecture

Local-first, single-user music release tracker. Three Python modules, one HTML page, no build step.

**Data flow:** Browser (vanilla JS) → FastAPI REST API → SQLite (via raw `sqlite3`) + MusicBrainz API (via async `httpx`).

- **`app.py`** — FastAPI entry point. Defines all `/api/*` endpoints and serves the Jinja2 template. The `/api/check` endpoint uses SSE (Server-Sent Events) via `StreamingResponse` to stream progress to the frontend.
- **`db.py`** — All database access. Each function opens/closes its own connection (`get_db()`). Schema has two tables: `artists` and `releases`, linked by `artist_id` FK with `ON DELETE CASCADE`. The `notified` column (0/1) tracks whether the user has seen a release.
- **`musicbrainz.py`** — Async MusicBrainz API client. Module-level `_last_request_time` enforces the mandatory 1 req/sec rate limit. Handles pagination for artists with many release groups.
- **`static/app.js`** — All frontend logic: tab switching, fetch calls to the API, SSE consumption for the check flow. No framework, no bundler.
- **`templates/index.html`** + **`static/style.css`** — Single-page shell with three tabs (Feed, Artists, Check). Dark theme.

## Key Design Decisions

- When an artist is first added, all their existing releases are imported with `notified=1` (already seen) so the feed isn't flooded. Only releases found in subsequent "Check Now" runs get `notified=0` (new).
- Uses `release-group` (not `release`) from MusicBrainz to avoid duplicates from regional editions/remasters.
- MusicBrainz dates are inconsistent ("YYYY", "YYYY-MM", "YYYY-MM-DD") — stored as-is, with `normalize_date_for_sort()` available for sorting.
- Database file is `music_releases.db` in the project root (gitignored if applicable).

## External API

MusicBrainz (`https://musicbrainz.org/ws/2/`): no API key needed, but requires a descriptive `User-Agent` header and max 1 request per second. Both are enforced in `musicbrainz.py`.
