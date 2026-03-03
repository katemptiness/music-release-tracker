from __future__ import annotations

import asyncio
import json
import webbrowser
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
import musicbrainz

HOST = "127.0.0.1"
PORT = 8080


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    webbrowser.open(f"http://{HOST}:{PORT}")
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Request models ---

class ArtistSearchRequest(BaseModel):
    query: str

class ArtistAddRequest(BaseModel):
    mbid: str
    name: str
    disambiguation: str = ""


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- Artist endpoints ---

@app.get("/api/artists")
async def list_artists():
    return db.get_all_artists()


@app.post("/api/artists/search")
async def search_artists(body: ArtistSearchRequest):
    results = await musicbrainz.search_artist(body.query)
    return results


@app.post("/api/artists")
async def add_artist(body: ArtistAddRequest):
    existing = db.get_artist_by_mbid(body.mbid)
    if existing:
        return {"status": "already_exists", "artist": existing}

    artist = db.add_artist(body.mbid, body.name, body.disambiguation)

    # Import all existing releases as already seen (notified=1)
    releases = await musicbrainz.get_artist_releases(body.mbid)
    count = 0
    for rel in releases:
        inserted = db.add_release(
            mbid=rel["mbid"],
            artist_id=artist["id"],
            title=rel["title"],
            release_type=rel["type"],
            release_date=rel["date"],
            notified=1,
        )
        if inserted:
            count += 1

    return {"status": "added", "artist": artist, "releases_imported": count}


@app.delete("/api/artists/{artist_id}")
async def remove_artist(artist_id: int):
    db.remove_artist(artist_id)
    return {"status": "removed"}


# --- Release endpoints ---

@app.get("/api/releases")
async def list_releases(
    artist_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    unseen_only: bool = Query(False),
):
    return db.get_releases(
        artist_id=artist_id,
        release_type=type,
        unseen_only=unseen_only,
    )


@app.post("/api/releases/{release_id}/seen")
async def mark_seen(release_id: int):
    db.mark_release_seen(release_id)
    return {"status": "ok"}


# --- Check endpoint (SSE) ---

@app.get("/api/check")
async def check_releases():
    async def event_stream():
        artists = db.get_all_artists()
        total = len(artists)

        if total == 0:
            yield _sse({"type": "done", "message": "No artists to check.", "summary": []})
            return

        summary = []

        for i, artist in enumerate(artists, 1):
            yield _sse({
                "type": "progress",
                "message": f"Checking artist {i} of {total}: {artist['name']}...",
                "current": i,
                "total": total,
            })

            try:
                releases = await musicbrainz.get_artist_releases(artist["mbid"])
            except Exception as e:
                yield _sse({
                    "type": "error",
                    "message": f"Error checking {artist['name']}: {e}",
                })
                continue

            new_count = 0
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
                    new_count += 1
                    new_titles.append(f"{rel['title']} ({rel['type']})")

            if new_count > 0:
                summary.append({
                    "artist": artist["name"],
                    "new_releases": new_titles,
                })

        total_new = sum(len(s["new_releases"]) for s in summary)
        yield _sse({
            "type": "done",
            "message": f"Done! Found {total_new} new release(s).",
            "summary": summary,
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn

    print(f"\n  Music Release Tracker")
    print(f"  Running at http://{HOST}:{PORT}\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
