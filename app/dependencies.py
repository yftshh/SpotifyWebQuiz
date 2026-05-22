"""Session and auth dependency injection."""

import time
from typing import Any

from fastapi import Request, HTTPException

from app.models.session import GameSession, RoundResult


def get_session(request: Request) -> dict[str, Any]:
    """Extract session dict from request (starlette SessionMiddleware)."""
    return dict(request.session)


def set_session(response: Any, session: dict[str, Any]) -> None:
    """No-op: starlette SessionMiddleware auto-saves request.session on response."""
    pass


def clear_session(response: Any) -> None:
    """No-op: session clearing is handled via request.session.clear() in the route."""
    pass


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
        current_target_preview_url=game_data.get("current_target_preview_url"),
        current_options=game_data.get("current_options", []),
        round_start_time_ms=game_data.get("round_start_time_ms", 0),
    )
    return game


def save_game_session(request: Request, game: GameSession) -> None:
    """Persist game state back into the session cookie."""
    request.session["game"] = {
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
        "current_target_preview_url": game.current_target_preview_url,
        "current_options": game.current_options,
        "round_start_time_ms": game.round_start_time_ms,
    }


def token_needs_refresh(session: dict[str, Any]) -> bool:
    """Check if the access token is expired or about to expire."""
    expires_at = session.get("expires_at", 0)
    return int(time.time()) >= (expires_at - 60)  # Refresh 60s before expiry
