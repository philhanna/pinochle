# pinochle.domain.team
from dataclasses import dataclass, field


@dataclass
class Team:
    """A two-player partnership and its accumulated score."""

    id: str
    name: str
    cumulative_score: int = field(default=0)

    def add_score(self, points: int) -> None:
        """Increase the cumulative team score by ``points``."""
        self.cumulative_score += points

    def subtract_score(self, points: int) -> None:
        """Decrease the cumulative team score by ``points``."""
        self.cumulative_score -= points
