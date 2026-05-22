"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, dashboard, game, leaderboard as leaderboard_router
from app.services.leaderboard import init_db


async def _init_db() -> None:
    """Initialize SQLite leaderboard on startup."""
    await init_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="SpotifyWebQuiz", version="1.0.0")

    # Session middleware (server-side signed cookies)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="spotifywebquiz_session",
        max_age=604800,  # 7 days
        same_site="lax",
        https_only=settings.environment == "production",
        path="/",
    )

    # Static assets
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Routers
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(game.router)
    app.include_router(leaderboard_router.router)

    @app.on_event("startup")
    async def startup() -> None:
        await _init_db()

    return app


app = create_app()
