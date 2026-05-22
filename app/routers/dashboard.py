"""Dashboard router: playlist selection."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_session, require_auth, token_needs_refresh
from app.services.spotify import get_user_playlists, refresh_access_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
                    session["refresh_token"] = token_data["refresh_token"]

    try:
        playlists = await get_user_playlists(access_token)
    except Exception:
        # Token may be invalid; force re-auth
        return RedirectResponse(url="/logout")

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "playlists": playlists,
            "access_token": access_token,
        },
    )
