"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import auth, dashboard, game


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="SpotifyWebQuiz", version="1.0.0")

    # Static assets
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Routers
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(game.router)

    return app


app = create_app()
