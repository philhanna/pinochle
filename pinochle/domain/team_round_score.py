# pinochle.domain.team_round_score
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamRoundScore:
    """One team's complete arithmetic for a single round.

    Carries everything FR-66 requires be shown after a round: what the team
    melded, what it captured, what the round came to, and where that left its
    cumulative score.  The breakdown is kept rather than a single figure
    because the round total and the points actually applied are different
    numbers whenever a team goes set or takes no trick at all.

    Attributes:
        team_id: The partnership this line belongs to, ``"NS"`` or ``"EW"``.
        meld: Meld recorded after the pass (FR-46), never recomputed later.
        card_points: Points captured in tricks, excluding the last-trick bonus.
        last_trick_bonus: 10 for the team that won the final trick, else 0.
        round_total: ``meld + card_points + last_trick_bonus`` (FR-61).
        points_applied: What was actually added to the cumulative score, which
            is negative for a team that went set (FR-63) or tossed the contract
            in (FR-50c), and zero for a non-bidding team that took no trick
            (FR-64).
        cumulative_score: The team's running total after this round.
    """

    team_id: str
    meld: int
    card_points: int
    last_trick_bonus: int
    round_total: int
    points_applied: int
    cumulative_score: int
