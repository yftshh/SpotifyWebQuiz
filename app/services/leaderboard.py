"""SQLite leaderboard service using aiosqlite."""

import asyncio
import os
from typing import Any

import aiosqlite

from app.config import settings

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "leaderboard.db")

_lock = asyncio.Lock()


def _get_db() -> aiosqlite.Connection:
    """Return a DB connection context manager."""
    return aiosqlite.connect(DB_PATH)


async def init_db() -> None:
    """Create leaderboard table if it doesn't exist."""
    async with _lock:
        async with _get_db() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    playlist_name TEXT,
                    score INTEGER NOT NULL,
                    accuracy REAL NOT NULL,
                    rounds INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()


async def add_score(
    player_name: str, playlist_name: str | None, score: int, accuracy: float, rounds: int
) -> None:
    """Insert a new game result."""
    async with _lock:
        async with _get_db() as db:
            await db.execute(
                """
                INSERT INTO leaderboard (player_name, playlist_name, score, accuracy, rounds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (player_name, playlist_name or "", score, accuracy, rounds),
            )
            await db.commit()


async def get_top_scores(limit: int = 50) -> list[dict[str, Any]]:
    """Return top scores ordered by score DESC."""
    async with _lock:
        async with _get_db() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT player_name, playlist_name, score, accuracy, rounds, created_at
                FROM leaderboard
                ORDER BY score DESC
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
