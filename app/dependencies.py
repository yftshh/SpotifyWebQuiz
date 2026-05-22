"""Session and auth dependency injection."""

import json
import time
from typing import Any

from fastapi import Request, HTTPException
from itsdangerous import URLSafeSerializer, BadSignature

from app.config import settings
from app.models.session import GameSession, RoundResult


SERIALIZER = URLSafeSerializer(settings.secret_key)
SESSION_COOKIE_NAME = "spotifywebquiz_session"


def _serialize_session(data: dict[str, Any]) -> str:
    """Serialize session dict to signed cookie string."""
    return SERIALIZER.dumps(data)


def _deserialize_session(cookie: str) -> dict[str, Any]:
    """Deserialize signed cookie string to session dict."""
    try:
        return SERIALIZER.loads(cookie)
    except BadSignature:
        return {}


def get_session(request: Request) -> dict[str, Any]:
    """Extract and decode the session from the request cookie."""
    cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not cookie:
        return {}
    return _deserialize_session(cookie)


def set_session(response: Any, session: dict[str, Any]) -> None:
    """Attach the signed session cookie to a response object."""
    # FastAPI Response / RedirectResponse has set_cookie method
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_serialize_session(session),
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )


def clear_session(response: Any) -> None:
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE_NAME)


def require_auth(request: Request) -> dict[str, Any]:
    """Dependency: ensure user is authenticated."""
    session = get_session(request)
    access_token = session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def get_game_session(request: Request) -> GameSession:
    """Dependency: retrieve or initialize game session from cookie."""
    session = get_session(request)
    game_data = session.get("game", {})
    game = GameSession(
        playlist_id=game_data.get("playlist_id", ""),
        tracks=game_data.get("tracks", []),
        played_track_ids=game_data.get("played_track_ids", []),
        current_round=game_data.get("current_round", 0),
        total_rounds=game_data.get("total_rounds", 10),
        score=game_data.get("score", 0),
        combo=game_data.get("combo", 0),
        round_results=[
            RoundResult(**r) for r in game_data.get("round_results", [])
        ],
        current_target_id=game_data.get("current_target_id"),
        current_target_uri=game_data.get("current_target_uri"),
        current_options=game_data.get("current_options", []),
        round_start_time_ms=game_data.get("round_start_time_ms", 0),
    )
    return game


def save_game_session(response: Any, session: dict[str, Any], game: GameSession) -> None:
    """Persist game state back into the session cookie."""
    session["game"] = {
        "playlist_id": game.playlist_id,
        "tracks": game.tracks,
        "played_track_ids": game.played_track_ids,
        "current_round": game.current_round,
        "total_rounds": game.total_rounds,
        "score": game.score,
        "combo": game.combo,
        "round_results": [
            {
                "track_id": r.track_id,
                "track_name": r.track_name,
                "artist_name": r.artist_name,
                "album_cover": r.album_cover,
                "correct": r.correct,
                "elapsed_ms": r.elapsed_ms,
                "points_earned": r.points_earned,
            }
            for r in game.round_results
        ],
        "current_target_id": game.current_target_id,
        "current_target_uri": game.current_target_uri,
        "current_options": game.current_options,
        "round_start_time_ms": game.round_start_time_ms,
    }
    set_session(response, session)


def token_needs_refresh(session: dict[str, Any]) -> bool:
    """Check if the access token is expired or about to expire."""
    expires_at = session.get("expires_at", 0)
    return int(time.time()) >= (expires_at - 60)  # Refresh 60s before expiry
