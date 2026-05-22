"""Authentication router: Spotify OAuth2 flow."""

import logging
import time
import urllib.parse
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

logger = logging.getLogger(__name__)

from app.config import settings
from app.dependencies import get_session, token_needs_refresh
from app.services.spotify import (
    AUTHORIZE_URL,
    SCOPES,
    exchange_code,
    refresh_access_token,
)

router = APIRouter()


@router.get("/login", response_model=None)
async def login(request: Request) -> RedirectResponse:
    """Redirect user to Spotify OAuth authorization page."""
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPES,
        "show_dialog": "true",
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@router.get("/callback", response_model=None)
async def callback(request: Request, code: str | None = None, error: str | None = None) -> RedirectResponse:
    """Handle Spotify OAuth callback and store tokens in session."""
    if error or not code:
        logger.warning("Spotify callback error: %s", error)
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    token_data = await exchange_code(code)
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    scope = token_data.get("scope", "")

    logger.info(
        "Spotify token exchange OK — access_token present=%s refresh_token present=%s scope=%s",
        bool(access_token),
        bool(refresh_token),
        scope,
    )

    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to retrieve access token")

    request.session["access_token"] = access_token
    request.session["refresh_token"] = refresh_token
    request.session["expires_at"] = int(time.time()) + expires_in

    logger.info("Callback redirecting to / with session cookie set")
    return RedirectResponse(url="/", status_code=302)


@router.post("/api/refresh-token")
async def api_refresh_token(request: Request) -> JSONResponse:
    """Refresh the Spotify access token and update the session cookie."""
    session = get_session(request)
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token available")

    token_data = await refresh_access_token(refresh_token)
    new_access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not new_access_token:
        raise HTTPException(status_code=400, detail="Token refresh failed")

    request.session["access_token"] = new_access_token
    if new_refresh_token:
        request.session["refresh_token"] = new_refresh_token
    request.session["expires_at"] = int(time.time()) + expires_in

    return JSONResponse({"access_token": new_access_token})


@router.get("/logout", response_model=None)
async def logout(request: Request) -> RedirectResponse:
    """Clear session and redirect to home."""
    request.session.clear()
    return RedirectResponse(url="/")


@router.get("/api/debug-session")
async def debug_session(request: Request) -> JSONResponse:
    """Return current session contents for troubleshooting (no secrets)."""
    session = get_session(request)
    return JSONResponse(
        {
            "has_access_token": bool(session.get("access_token")),
            "has_refresh_token": bool(session.get("refresh_token")),
            "expires_at": session.get("expires_at"),
            "cookie_present": bool(request.cookies.get("spotifywebquiz_session")),
        }
    )
