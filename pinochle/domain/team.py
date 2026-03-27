# pinochle.domain.team
from dataclasses import dataclass, field


@dataclass
class Team:
    id: str
    name: str
    cumulative_score: int = field(default=0)

    def add_score(self, points: int) -> None:
        self.cumulative_score += points

    def subtract_score(self, points: int) -> None:
        self.cumulative_score -= points
