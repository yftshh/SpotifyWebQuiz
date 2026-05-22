"""Authentication router: Spotify OAuth2 flow."""

import time
import urllib.parse
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.dependencies import (
    get_session,
    set_session,
    clear_session,
    token_needs_refresh,
)
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
        "show_dialog": "false",
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@router.get("/callback", response_model=None)
async def callback(request: Request, code: str | None = None, error: str | None = None) -> RedirectResponse:
    """Handle Spotify OAuth callback and store tokens in session."""
    if error or not code:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    token_data = await exchange_code(code)
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to retrieve access token")

    session = get_session(request)
    session["access_token"] = access_token
    session["refresh_token"] = refresh_token
    session["expires_at"] = int(time.time()) + expires_in

    response = RedirectResponse(url="/")
    set_session(response, session)
    return response


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

    session["access_token"] = new_access_token
    if new_refresh_token:
        session["refresh_token"] = new_refresh_token
    session["expires_at"] = int(time.time()) + expires_in

    response = JSONResponse({"access_token": new_access_token})
    set_session(response, session)
    return response


@router.get("/logout", response_model=None)
async def logout() -> RedirectResponse:
    """Clear session and redirect to home."""
    response = RedirectResponse(url="/")
    clear_session(response)
    return response
