"""Leaderboard router: menu page, leaderboard page, and score submission."""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_session
from app.services.leaderboard import add_score, get_top_scores

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/menu", response_class=HTMLResponse)
async def menu_page(request: Request) -> HTMLResponse:
    """Post-login menu with Play and Leaderboard buttons."""
    session = get_session(request)
    if not session.get("access_token"):
        return RedirectResponse(url="/", status_code=302)

    player_name = session.get("player_name", "Player")
    return templates.TemplateResponse(
        "menu.html",
        {"request": request, "player_name": player_name},
    )


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request) -> HTMLResponse:
    """Global leaderboard page."""
    scores = await get_top_scores(limit=50)
    return templates.TemplateResponse(
        "leaderboard.html",
        {"request": request, "scores": scores},
    )


@router.post("/api/leaderboard/submit")
async def submit_score(request: Request) -> dict[str, Any]:
    """Submit a game result to the leaderboard."""
    session = get_session(request)
    player_name = session.get("player_name", "Anonymous")
    playlist_name = session.get("playlist_name")
    score = session.get("score", 0)
    total_rounds = session.get("total_rounds", 0)
    accuracy = round((score / total_rounds) * 100, 1) if total_rounds else 0.0

    await add_score(
        player_name=player_name,
        playlist_name=playlist_name,
        score=score,
        accuracy=accuracy,
        rounds=total_rounds,
    )
    logger.info("Score submitted: %s scored %s/%s", player_name, score, total_rounds)
    return {"status": "ok"}
