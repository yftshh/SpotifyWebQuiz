"""Server-side session state models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoundResult:
    """Result of a single game round."""

    track_id: str
    track_name: str
    artist_name: str
    album_cover: str
    correct: bool
    elapsed_ms: int
    points_earned: int


@dataclass
class GameSession:
    """Mutable game state stored in the server-side session."""

    playlist_id: str = ""
    tracks: list[dict[str, Any]] = field(default_factory=list)
    played_track_ids: list[str] = field(default_factory=list)
    current_round: int = 0
    total_rounds: int = 10
    score: int = 0
    combo: int = 0
    round_results: list[RoundResult] = field(default_factory=list)
    current_target_id: str | None = None
    current_target_uri: str | None = None
    current_target_preview_url: str | None = None
    current_options: list[dict[str, Any]] = field(default_factory=list)
    round_start_time_ms: int = 0

    def is_game_over(self) -> bool:
        """Return True if all rounds have been played."""
        return self.current_round >= self.total_rounds

    def get_anthem(self) -> RoundResult | None:
        """Return the correct answer with the fastest reaction time."""
        correct = [r for r in self.round_results if r.correct]
        if not correct:
            return None
        return min(correct, key=lambda r: r.elapsed_ms)

    def get_kryptonite(self) -> RoundResult | None:
        """Return the wrong/timed-out answer with the longest duration."""
        wrong = [r for r in self.round_results if not r.correct]
        if not wrong:
            return None
        return max(wrong, key=lambda r: r.elapsed_ms)

    def accuracy_pct(self) -> float:
        """Calculate accuracy percentage."""
        if not self.round_results:
            return 0.0
        correct_count = sum(1 for r in self.round_results if r.correct)
        return round((correct_count / len(self.round_results)) * 100, 1)
