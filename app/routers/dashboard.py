"""Dashboard router: playlist selection."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_session, token_needs_refresh
from app.services.spotify import get_user_playlists, refresh_access_token, SpotifyQuotaError, SpotifyAuthError, get_liked_tracks_count

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse, response_model=None)
async def dashboard(request: Request) -> HTMLResponse | RedirectResponse:
    """Render login page if unauthorized, otherwise show playlist grid."""
    session = get_session(request)
    access_token = session.get("access_token")

    if not access_token:
        return templates.TemplateResponse(request, "login.html", {})

    # Refresh token if needed before fetching playlists
    if token_needs_refresh(session):
        refresh_token = session.get("refresh_token")
        if refresh_token:
            token_data = await refresh_access_token(refresh_token)
            new_access = token_data.get("access_token")
            if new_access:
                access_token = new_access
                session["access_token"] = new_access
                if token_data.get("refresh_token"):
                    session["refresh_token"] = token_data.get("refresh_token")

    try:
        playlists = await get_user_playlists(access_token)
    except SpotifyQuotaError as exc:
        logger.warning("Spotify quota error (app not approved for public use): %s", exc)
        return templates.TemplateResponse(
            request,
            "quota_error.html",
            {},
            status_code=403,
        )
    except SpotifyAuthError as exc:
        logger.warning("Spotify auth error (missing scope or expired token): %s", exc)
        # Force re-authorisation so user can grant required scopes
        return RedirectResponse(url="/login")
    except Exception:
        logger.exception("Failed to fetch user playlists")
        # Unexpected error — keep session and show generic error page
        return templates.TemplateResponse(
            request,
            "error.html",
            {"detail": "Unable to load playlists. Please try again later."},
            status_code=500,
        )

    # Inject virtual "Liked Songs" playlist at the top if user has saved tracks
    try:
        liked_count = await get_liked_tracks_count(access_token)
    except Exception:
        liked_count = 0

    if liked_count >= 10:
        liked_playlist = {
            "id": "liked-songs",
            "name": "Liked Songs",
            "images": [{"url": ""}],  # template will render a heart fallback
            "tracks": {"total": liked_count},
        }
        playlists.insert(0, liked_playlist)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "playlists": playlists,
            "access_token": access_token,
        },
    )
