from __future__ import annotations

import asyncio
import time

import httpx

BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "MusicReleaseTracker/0.1.0 (https://github.com/placeholder)"

_last_request_time: float = 0.0
_lock = asyncio.Lock()
_client: httpx.AsyncClient = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
        )
    return _client


async def _rate_limited_get(url: str, params: dict) -> dict:
    """Make a GET request with rate limiting and serialization."""
    global _last_request_time
    async with _lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _last_request_time = time.monotonic()

        client = _get_client()
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def search_artist(query: str) -> list[dict]:
    """Search MusicBrainz for artists matching the query."""
    data = await _rate_limited_get(
        f"{BASE_URL}/artist/",
        params={"query": query, "fmt": "json"},
    )

    results = []
    for artist in data.get("artists", []):
        results.append({
            "mbid": artist["id"],
            "name": artist.get("name", ""),
            "disambiguation": artist.get("disambiguation", ""),
            "type": artist.get("type", ""),
            "country": artist.get("country", ""),
            "score": artist.get("score", 0),
        })
    return results


async def get_artist_releases(mbid: str) -> list[dict]:
    """Fetch official album and EP release groups for an artist.

    Uses the /release endpoint with status=official and inc=release-groups,
    then deduplicates by release group ID. This filters out bootlegs and
    unofficial releases that the /release-group endpoint cannot distinguish.
    """
    seen_rg_ids = set()
    all_releases = []
    offset = 0
    limit = 100

    while True:
        data = await _rate_limited_get(
            f"{BASE_URL}/release",
            params={
                "artist": mbid,
                "type": "album|ep",
                "status": "official",
                "inc": "release-groups",
                "fmt": "json",
                "limit": limit,
                "offset": offset,
            },
        )

        for release in data.get("releases", []):
            rg = release.get("release-group", {})
            rg_id = rg.get("id", "")
            if not rg_id or rg_id in seen_rg_ids:
                continue
            seen_rg_ids.add(rg_id)

            primary_type = rg.get("primary-type", "")
            if primary_type not in ("Album", "EP"):
                continue
            if rg.get("secondary-types"):
                continue

            all_releases.append({
                "mbid": rg_id,
                "title": rg.get("title", ""),
                "type": primary_type,
                "date": rg.get("first-release-date", ""),
            })

        total = data.get("release-count", 0)
        offset += limit
        if offset >= total:
            break

    return all_releases


def normalize_date_for_sort(date_str: str) -> str:
    """Pad incomplete dates for consistent sorting.
    '2024' -> '2024-00-00', '2024-06' -> '2024-06-00', '' -> '0000-00-00'
    """
    if not date_str:
        return "0000-00-00"
    parts = date_str.split("-")
    while len(parts) < 3:
        parts.append("00")
    return "-".join(parts)
