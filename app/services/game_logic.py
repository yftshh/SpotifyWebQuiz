"""Game mechanics: track selection, scoring, and round generation."""

import random
import time
from typing import Any

from app.models.session import GameSession, RoundResult


def generate_round(game: GameSession) -> dict[str, Any]:
    """Select target + 3 decoys and update game session state."""
    available = [t for t in game.tracks if t["id"] not in game.played_track_ids]
    if len(available) < 4:
        # Not enough tracks left; reset played pool (shouldn't happen with 10 rounds)
        available = game.tracks.copy()

    # Target must have a preview_url so it can be played
    targets_with_preview = [t for t in available if t.get("preview_url")]
    if not targets_with_preview:
        raise ValueError("No tracks with preview available")
    target = random.choice(targets_with_preview)
    game.played_track_ids.append(target["id"])
    game.current_target_id = target["id"]
    game.current_target_uri = target["uri"]
    game.current_target_preview_url = target.get("preview_url")
    game.current_round += 1

    # Select 3 unique decoys
    decoy_pool = [t for t in available if t["id"] != target["id"]]
    decoys = random.sample(decoy_pool, min(3, len(decoy_pool)))

    options = [target, *decoys]
    random.shuffle(options)

    # Obfuscate options for frontend: only id, name, artist
    game.current_options = [
        {"id": opt["id"], "name": opt["name"], "artist": opt["artist"]}
        for opt in options
    ]

    game.round_start_time_ms = int(time.time() * 1000)

    return {
        "round": game.current_round,
        "total_rounds": game.total_rounds,
        "target_uri": target["uri"],
        "target_preview_url": target.get("preview_url"),
        "options": game.current_options,
        "combo": game.combo,
        "score": game.score,
    }


def calculate_points(elapsed_ms: int, combo: int, fever_mode: bool) -> int:
    """Calculate points based on speed and combo."""
    base = 100
    # Time bonus: faster = more points (max 15s)
    time_bonus = max(0, 15000 - elapsed_ms) / 15000  # 0.0 - 1.0
    points = int(base + (base * time_bonus))
    points *= combo
    if fever_mode:
        points *= 2
    return points


def process_answer(
    game: GameSession, choice_id: str, elapsed_ms: int
) -> dict[str, Any]:
    """Validate answer, update score/combo, and return result payload."""
    correct = choice_id == game.current_target_id

    if correct:
        game.combo += 1
    else:
        game.combo = 0

    fever_mode = game.combo >= 3
    points = calculate_points(elapsed_ms, game.combo, fever_mode) if correct else 0
    game.score += points

    # Find track metadata for result storage
    target_track = next(
        (t for t in game.tracks if t["id"] == game.current_target_id), {}
    )

    result = RoundResult(
        track_id=game.current_target_id or "",
        track_name=target_track.get("name", "Unknown"),
        artist_name=target_track.get("artist", "Unknown"),
        album_cover=target_track.get("album_cover", ""),
        correct=correct,
        elapsed_ms=elapsed_ms,
        points_earned=points,
    )
    game.round_results.append(result)

    # Find correct option details for frontend reveal
    correct_option = next(
        (opt for opt in game.current_options if opt["id"] == game.current_target_id), {}
    )

    return {
        "correct": correct,
        "points": points,
        "combo": game.combo,
        "fever_mode": fever_mode,
        "total_score": game.score,
        "correct_id": game.current_target_id,
        "album_cover": target_track.get("album_cover", ""),
        "track_name": target_track.get("name", ""),
        "artist_name": target_track.get("artist", ""),
        "correct_option": correct_option,
    }
