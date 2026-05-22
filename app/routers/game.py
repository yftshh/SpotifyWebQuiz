"""Game router: game arena, answer validation, and results."""

import logging
import random

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import (
    get_session,
    get_game_session,
    save_game_session,
    token_needs_refresh,
)
from app.models.session import GameSession
from app.services.spotify import (
    get_playlist_tracks,
    get_liked_tracks,
    refresh_access_token,
    SpotifyAuthError,
    SpotifyQuotaError,
)
from app.services.game_logic import generate_round, process_answer

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


async def _ensure_token(request: Request) -> str:
    """Helper to get/refresh access token from session."""
    session = get_session(request)
    access_token = session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if token_needs_refresh(session):
        refresh_token = session.get("refresh_token")
        if refresh_token:
            token_data = await refresh_access_token(refresh_token)
            new_access = token_data.get("access_token")
            if new_access:
                access_token = new_access
                request.session["access_token"] = new_access
                if token_data.get("refresh_token"):
                    request.session["refresh_token"] = token_data["refresh_token"]
    return access_token


@router.get("/game/{playlist_id}", response_class=HTMLResponse, response_model=None)
async def game_arena(request: Request, playlist_id: str) -> HTMLResponse | RedirectResponse:
    """Initialize or resume a game for the given playlist."""
    access_token = await _ensure_token(request)
    game = get_game_session(request)

    # If starting a new game or switching playlists, reset state
    if game.playlist_id != playlist_id or game.is_game_over():
        try:
            if playlist_id == "liked-songs":
                tracks = await get_liked_tracks(access_token)
            else:
                tracks = await get_playlist_tracks(access_token, playlist_id)
        except SpotifyAuthError:
            return RedirectResponse(url="/login")
        except SpotifyQuotaError as exc:
            raise HTTPException(
                status_code=403,
                detail=f"Spotify quota error: {exc}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load playlist tracks: {exc}",
            )

        if len(tracks) < 4:
            raise HTTPException(
                status_code=400,
                detail="Playlist must contain at least 4 tracks.",
            )

        # Cap tracks stored in session to avoid cookie overflow
        if len(tracks) > 100:
            tracks = random.sample(tracks, 100)
            if len(tracks) < 4:
                raise HTTPException(
                    status_code=400,
                    detail="Playlist must contain at least 4 tracks.",
                )

        game = GameSession(
            playlist_id=playlist_id,
            tracks=tracks,
            total_rounds=min(10, len(tracks)),
        )

    # Generate the current round data (or first round if new / corrupted)
    if game.current_round == 0 or not game.current_target_id or not game.current_options:
        logger.info("Generating new round for playlist=%s round=%s target_id=%s", playlist_id, game.current_round, game.current_target_id)
        round_data = await generate_round(game)
    else:
        # Resume existing round
        logger.info("Resuming round for playlist=%s round=%s target_id=%s", playlist_id, game.current_round, game.current_target_id)
        round_data = {
            "round": game.current_round,
            "total_rounds": game.total_rounds,
            "target_uri": game.current_target_uri,
            "target_preview_url": game.current_target_preview_url,
            "options": game.current_options,
            "combo": game.combo,
            "score": game.score,
        }

    # Persist game state
    save_game_session(request, game)
    return templates.TemplateResponse(
        request,
        "game.html",
        {
            "round_data": round_data,
        },
    )


@router.post("/api/check-answer")
async def check_answer(request: Request) -> JSONResponse:
    """Validate user's card choice. Anti-cheat: correctness determined server-side."""
    body = await request.json()
    choice_id: str = body.get("choice_id", "")
    elapsed_ms: int = body.get("elapsed_ms", 15000)

    game = get_game_session(request)
    logger.info("check-answer: round=%s target_id=%s tracks=%s played=%s", game.current_round, game.current_target_id, len(game.tracks), len(game.played_track_ids))

    if not game.current_target_id:
        # Attempt to recover if tracks exist but round wasn't initialized
        if game.tracks and len(game.tracks) >= 4:
            logger.warning("No active round but tracks exist; regenerating round")
            round_data = await generate_round(game)
            save_game_session(request, game)
            # Return current round data so client can retry
            return JSONResponse({**round_data, "game_over": False, "recovered": True})
        raise HTTPException(status_code=400, detail="No active round")

    result = process_answer(game, choice_id, elapsed_ms)

    # If game over, persist final state and return flag
    is_over = game.is_game_over()

    save_game_session(request, game)
    return JSONResponse({**result, "game_over": is_over})


@router.get("/api/next-round")
async def next_round(request: Request) -> JSONResponse:
    """Generate the next round and return round data."""
    game = get_game_session(request)

    if game.is_game_over():
        return JSONResponse({"game_over": True})

    round_data = await generate_round(game)
    save_game_session(request, game)
    return JSONResponse({**round_data, "game_over": False})


@router.get("/results", response_class=HTMLResponse, response_model=None)
async def results(request: Request) -> HTMLResponse | RedirectResponse:
    """Render the endgame analytics screen."""
    game = get_game_session(request)

    if not game.round_results:
        return RedirectResponse(url="/")

    anthem = game.get_anthem()
    kryptonite = game.get_kryptonite()

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "score": game.score,
            "accuracy": game.accuracy_pct(),
            "anthem": anthem,
            "kryptonite": kryptonite,
            "round_results": game.round_results,
        },
    )
