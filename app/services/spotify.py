"""Async Spotify API client using httpx."""

import base64
from typing import Any

import httpx

from app.config import settings


SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"

SCOPES = " ".join(
    [
        "user-read-private",
        "user-read-email",
        "playlist-read-private",
        "user-read-playback-state",
        "streaming",
        "user-modify-playback-state",
    ]
)


def _basic_auth_header() -> str:
    """Generate Base64-encoded client credentials."""
    credentials = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()
    return f"Basic {credentials}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange authorization code for access/refresh tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_AUTH_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
            headers={"Authorization": _basic_auth_header()},
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_AUTH_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Authorization": _basic_auth_header()},
        )
        response.raise_for_status()
        return response.json()


class SpotifyAPIError(Exception):
    """Base exception for Spotify API errors."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class SpotifyAuthError(SpotifyAPIError):
    """Raised when the user is not authorised or token is invalid."""
    pass


class SpotifyQuotaError(SpotifyAPIError):
    """Raised when the app is in Development Mode and the user is not whitelisted."""
    pass


async def spotify_api_get(
    endpoint: str, access_token: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Generic authenticated GET to Spotify Web API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPOTIFY_API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=30.0,
        )
        if response.status_code in (401, 403):
            body = response.text or ""
            if "not registered for this application" in body:
                raise SpotifyQuotaError(
                    f"Spotify API {endpoint} returned {response.status_code}: {body}",
                    status_code=response.status_code,
                )
            raise SpotifyAuthError(
                f"Spotify API {endpoint} returned {response.status_code}: {body}",
                status_code=response.status_code,
            )
        response.raise_for_status()
        return response.json()


async def get_user_playlists(access_token: str) -> list[dict[str, Any]]:
    """Fetch user playlists and filter out those with < 10 tracks."""
    data = await spotify_api_get("/me/playlists", access_token, {"limit": 50})
    items = data.get("items", [])
    return [pl for pl in items if pl.get("tracks", {}).get("total", 0) >= 10]


async def get_playlist_tracks(access_token: str, playlist_id: str) -> list[dict[str, Any]]:
    """Fetch all tracks from a playlist with valid URIs."""
    tracks: list[dict[str, Any]] = []
    offset = 0
    limit = 100

    while True:
        data = await spotify_api_get(
            f"/playlists/{playlist_id}/tracks",
            access_token,
            {"limit": limit, "offset": offset},
        )
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            track = item.get("track")
            if not track:
                continue
            if track.get("is_local"):
                continue
            uri = track.get("uri")
            if not uri or not uri.startswith("spotify:track:"):
                continue
            # Ensure we have preview data / name
            name = track.get("name")
            if not name:
                continue

            album = track.get("album", {})
            images = album.get("images", [])
            cover_url = images[0]["url"] if images else ""

            artists = track.get("artists", [])
            artist_name = artists[0]["name"] if artists else "Unknown Artist"

            tracks.append(
                {
                    "id": track["id"],
                    "uri": uri,
                    "name": name,
                    "artist": artist_name,
                    "album_cover": cover_url,
                }
            )

        if len(items) < limit:
            break
        offset += limit

    return tracks


async def start_playback(access_token: str, device_id: str, track_uri: str) -> None:
    """Start playback of a track on the given device via Spotify Web API."""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{SPOTIFY_API_BASE}/me/player/play",
            params={"device_id": device_id},
            json={"uris": [track_uri]},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        # 204 No Content is success; 404 may mean device not found yet
        if response.status_code not in (204, 200):
            response.raise_for_status()
