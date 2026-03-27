# pinochle.domain.scoring
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.trick import Trick

# Cards worth points in trick-taking
_TRICK_POINTS: dict[Rank, int] = {
    Rank.ACE: 10,
    Rank.TEN: 10,
    Rank.KING: 5,
    Rank.QUEEN: 5,
    Rank.JACK: 0,
    Rank.NINE: 0,
}

LAST_TRICK_BONUS = 10
WINNING_SCORE = 2000


def score_cards(cards: list[Card]) -> int:
    """Return the point value of a list of captured cards (no last-trick bonus)."""
    return sum(_TRICK_POINTS[c.rank] for c in cards)


def score_tricks(tricks: list[Trick], last_trick_winner_id: str, player_team: dict[str, str]) -> dict[str, int]:
    """Return a mapping of team_id -> trick points (including last-trick bonus).

    Args:
        tricks: All completed tricks in a round.
        last_trick_winner_id: Player who won the final trick.
        player_team: Mapping of player_id -> team_id.
    """
    team_scores: dict[str, int] = {}
    for trick in tricks:
        winner = trick.winner()
        team = player_team[winner]
        team_scores[team] = team_scores.get(team, 0) + score_cards(trick.cards)

    last_team = player_team[last_trick_winner_id]
    team_scores[last_team] = team_scores.get(last_team, 0) + LAST_TRICK_BONUS

    return team_scores


def resolve_round(
    trick_scores: dict[str, int],
    meld_scores: dict[str, int],
    bid_team_id: str,
    contract: int,
) -> dict[str, int]:
    """Return net points awarded to each team for this round.

    The bidding team earns their meld + trick points only if they met
    the contract; otherwise they lose the contract value and their meld
    (going set). The non-bidding team always keeps meld if they took at
    least one trick.

    Args:
        trick_scores: team_id -> trick points earned this round.
        meld_scores: team_id -> total meld points this round.
        bid_team_id: The team that won the bid.
        contract: The bid amount to be met.
    """
    net: dict[str, int] = {}
    for team_id in meld_scores:
        tricks = trick_scores.get(team_id, 0)
        meld = meld_scores[team_id]
        if team_id == bid_team_id:
            total = tricks + meld
            if total >= contract:
                net[team_id] = total
            else:
                # Going set: lose contract value and meld
                net[team_id] = -(contract + meld)
        else:
            # Non-bidding team: keep meld only if they took at least one trick
            if tricks > 0:
                net[team_id] = tricks + meld
            else:
                net[team_id] = 0
    return net
