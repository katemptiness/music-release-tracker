# Music Release Tracker — Project Spec

## Overview

A local desktop application that tracks new album and EP releases from artists the user follows. The app runs entirely on the user's machine — no remote server or hosting. It uses MusicBrainz as its data source and presents a local web UI in the browser.

## Core Principles

- **Local-first**: Everything runs on localhost. No deployment, no auth, no cloud.
- **Simple to launch**: The user runs a single Python script (or a shell command), and the app opens in their default browser.
- **Future-proof UI**: Using a local web interface (not a native GUI) so the app can later be hosted or turned into a PWA with minimal rewrite.
- **Respectful API usage**: MusicBrainz requires a descriptive `User-Agent` header and a rate limit of **1 request per second**. No API key is needed.

## Tech Stack

- **Language**: Python 3.10+
- **Web framework**: NiceGUI, Flask, or FastAPI — pick whichever produces the cleanest result for this use case. If using Flask/FastAPI, include a minimal frontend (HTML/CSS/JS) bundled with the project.
- **Database**: SQLite via `sqlite3` or SQLAlchemy (developer's choice).
- **HTTP client**: `requests` or `httpx` for MusicBrainz API calls.
- **No external services**: No Docker, no Redis, no Postgres, no remote APIs other than MusicBrainz.

## Data Source: MusicBrainz API

Base URL: `https://musicbrainz.org/ws/2/`

### Artist Search

```
GET /ws/2/artist/?query={name}&fmt=json
```

Returns a list of matching artists. Each result includes:
- `id` (MBID) — unique identifier
- `name`
- `disambiguation` — helpful when multiple artists share a name (e.g., "British rock band" vs "American DJ")
- `type` — Person, Group, etc.
- `country`

### Release Groups by Artist

```
GET /ws/2/release-group/?artist={mbid}&type=album|ep&fmt=json&limit=100&offset=0
```

Key fields:
- `id` — release group MBID
- `title`
- `primary-type` — "Album" or "EP" (filter to these two only; ignore "Single", "Broadcast", "Other")
- `first-release-date` — format varies: "YYYY", "YYYY-MM", or "YYYY-MM-DD"

**Important**: Use `release-group` (not `release`) to avoid duplicates from regional editions, remasters, etc. A release group represents the abstract album/EP itself.

### Rate Limiting

- Maximum **1 request per second**. Enforce a delay between consecutive API calls.
- Set a custom `User-Agent` header, e.g.:
  `MusicReleaseTracker/0.1.0 (https://github.com/placeholder)`

## Database Schema

### `artists`

| Column          | Type    | Description                        |
|-----------------|---------|------------------------------------|
| id              | INTEGER | Primary key, autoincrement         |
| mbid            | TEXT    | MusicBrainz artist ID (unique)     |
| name            | TEXT    | Artist display name                |
| disambiguation  | TEXT    | MusicBrainz disambiguation string  |
| added_at        | TEXT    | ISO 8601 timestamp                 |

### `releases`

| Column          | Type    | Description                              |
|-----------------|---------|------------------------------------------|
| id              | INTEGER | Primary key, autoincrement               |
| mbid            | TEXT    | MusicBrainz release group ID (unique)    |
| artist_id       | INTEGER | FK → artists.id                          |
| title           | TEXT    | Album or EP title                        |
| release_type    | TEXT    | "Album" or "EP"                          |
| release_date    | TEXT    | First release date (as provided by MB)   |
| first_seen_at   | TEXT    | ISO 8601 timestamp of when we first discovered this release |
| notified        | INTEGER | 0 or 1 — whether the user has seen this |

## Features

### 1. Artist Management

**Add Artist**:
- A text input field + "Search" button.
- On submit, query MusicBrainz artist search.
- If exactly **one** result matches confidently, add it directly.
- If **multiple** results are found, display a disambiguation list showing: name, disambiguation string, type, and country. Let the user pick the correct one.
- If **no results**, show a message.
- On selection, save the artist to the database and immediately fetch their releases.

**View Artists**:
- A list/table of all tracked artists.
- Each entry has a "Remove" button/action.

### 2. Release Checking

**"Check Now" button**:
- Iterates over all saved artists.
- For each artist, fetches their release groups (albums + EPs) from MusicBrainz.
- Compares against the database:
  - New releases (MBID not in DB) are inserted with `notified = 0`.
  - Existing releases are left unchanged.
- After the check, display results: how many new releases were found, listed by artist.
- Respect the 1 req/sec rate limit. Show progress during the check (e.g., "Checking artist 3 of 12...").

### 3. Release Feed

- A main view showing releases, sorted by `release_date` descending (newest first).
- Each entry shows: **Artist — Title** (Type) · Release Date
- Highlight or badge entries where `notified = 0` (i.e., newly discovered since last check). Clicking/viewing them marks them as seen.
- Basic filtering: by artist, by type (Album / EP), or show only new/unseen.

## UI/UX Guidelines

- Clean, minimal interface. Dark theme preferred.
- Three main sections/tabs:
  1. **Feed** — the release list (default/home view)
  2. **Artists** — manage tracked artists
  3. **Check** — the "Check Now" action + results log
- The UI should feel responsive and snappy. Use async where beneficial.
- No login, no user accounts. Single-user app.

## Project Structure (suggested)

```
music-release-tracker/
├── app.py              # Entry point — starts the local server and opens browser
├── db.py               # Database init, connection, queries
├── musicbrainz.py      # MusicBrainz API client with rate limiting
├── models.py           # Data classes or ORM models (if using SQLAlchemy)
├── requirements.txt
├── README.md
└── static/             # If using Flask/FastAPI: HTML, CSS, JS
    └── ...
```

## Launch Behavior

- Running `python app.py` should:
  1. Initialize the SQLite database (create tables if they don't exist).
  2. Start the local web server on an available port (default: `8080` or similar).
  3. Automatically open the user's default browser to `http://localhost:{port}`.
- Stopping the script (Ctrl+C) shuts everything down cleanly.

## Out of Scope (for now)

These are explicitly **not** part of the initial version:
- Notifications (push, email, desktop)
- Scheduled/automatic background checking
- Remote hosting or multi-user support
- Mobile/PWA features
- Spotify or Last.fm integration
- Album artwork fetching
- Release details beyond what MusicBrainz provides

## Notes for the Developer

- MusicBrainz date formats are inconsistent ("2024", "2024-06", "2024-06-14"). Handle all three gracefully in sorting and display.
- Some artists have hundreds of release groups. Paginate the API calls (100 per page) and handle offsets.
- The `first_seen_at` field matters: it lets us distinguish "new to the user" from "new in general." An album from 2019 discovered on first sync is not the same as a genuinely new 2025 release — but both should appear, just without the "new" badge for old ones on initial import.
- On first add of an artist, all their existing releases should be imported with `notified = 1` (already seen), so the feed isn't flooded. Only releases discovered in *subsequent* checks should be marked as new.
