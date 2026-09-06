# tests.services.test_game_service
import pytest

from pinochle.adapters.immediate_scheduler import ImmediateScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import GamePhase
from pinochle.services.round import Round, RoundPhase
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import Team
from pinochle.services.game_service import GameService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEAMS = [
    Team("NS", "North-South"),
    Team("EW", "East-West"),
]

PLAYERS = [
    Player("N", "North", PlayerType.HUMAN, Position.NORTH, "NS"),
    Player("E", "East",  PlayerType.HUMAN, Position.EAST,  "EW"),
    Player("S", "South", PlayerType.HUMAN, Position.SOUTH, "NS"),
    Player("W", "West",  PlayerType.HUMAN, Position.WEST,  "EW"),
]


def make_service() -> tuple[GameService, InMemoryGameState]:
    """Create a game service wired to in-memory test adapters."""
    state = InMemoryGameState()
    notifier = PrintNotification()
    return GameService(state, notifier, ImmediateScheduler()), state


def setup_game(service: GameService) -> str:
    """Create a game, add teams and players, and start dealer selection."""
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    for player in PLAYERS:
        service.add_player(game_id, player)
    service.start_game(game_id)
    return game_id


# ---------------------------------------------------------------------------
# AdminPort
# ---------------------------------------------------------------------------

def test_create_game_returns_id():
    """Creating a game should return a persisted non-empty id."""
    service, state = make_service()
    game_id = service.create_game()
    assert isinstance(game_id, str) and len(game_id) > 0
    assert state.load(game_id).id == game_id


def test_add_player_registered():
    """Added players should appear in persisted game state."""
    service, state = make_service()
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    service.add_player(game_id, PLAYERS[0])
    game = state.load(game_id)
    assert "N" in game.players


def test_assign_teams():
    """Assigned team ids should be stored on the game aggregate."""
    service, state = make_service()
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    game = state.load(game_id)
    assert "NS" in game.teams
    assert "EW" in game.teams


def test_start_game_enters_dealer_selection():
    """Starting a fully configured game should enter dealer selection."""
    service, state = make_service()
    game_id = setup_game(service)
    game = state.load(game_id)
    assert game.phase == GamePhase.DEALER_SELECTION


# ---------------------------------------------------------------------------
# draw_for_deal — dealer selection
# ---------------------------------------------------------------------------

def test_draw_for_deal_returns_card():
    """A dealer-selection draw should return the dealt card."""
    service, state = make_service()
    game_id = setup_game(service)
    card = service.draw_for_deal(game_id, "N")
    assert card is not None


def test_all_four_draws_starts_round():
    """Four dealer-selection draws should resolve or trigger a redraw."""
    service, state = make_service()
    game_id = setup_game(service)
    for pid in ["N", "E", "S", "W"]:
        service.draw_for_deal(game_id, pid)
    # After all four draw, game either re-draws (tie) or moves to IN_ROUND
    game = state.load(game_id)
    assert game.phase in (GamePhase.DEALER_SELECTION, GamePhase.IN_ROUND)


# ---------------------------------------------------------------------------
# PlayerActionPort — bidding
# ---------------------------------------------------------------------------

def _advance_to_bidding(service: GameService, state: InMemoryGameState) -> str:
    """Set up a game and force past dealer selection."""
    game_id = setup_game(service)
    game = state.load(game_id)
    game.phase = GamePhase.DEALER_SELECTION
    game.set_dealer("N")
    round_state = Round(dealer_id="N", player_order=["N", "E", "S", "W"])
    round_state.deal()
    game.begin_round(round_state)
    game.pop_events()
    state.save(game)
    return game_id


def test_place_bid_recorded():
    """Bids placed through the service should update the round bidding state."""
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    # Bid order starts left of dealer (N), so E bids first
    service.place_bid(game_id, "E", 250)
    game = state.load(game_id)
    assert game.current_round._bidding.current_high == 250


def test_place_bid_pass_recorded():
    """Passing through the service should remove the player from active bidding."""
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    service.place_bid(game_id, "E", None)
    game = state.load(game_id)
    assert "E" not in game.current_round._bidding.active_players


# ---------------------------------------------------------------------------
# Events are dispatched via notifier
# ---------------------------------------------------------------------------

def test_events_broadcast(capsys):
    """Service actions should dispatch emitted events through the notifier."""
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    service.place_bid(game_id, "E", 250)
    output = capsys.readouterr().out
    assert "BidPlaced" in output


# ---------------------------------------------------------------------------
# _resolve_draw
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Passing, meld, and the transition into trick play
# ---------------------------------------------------------------------------

def _advance_to_passing(service: GameService, state: InMemoryGameState) -> str:
    """Set up a game where E has won the auction and named spades trump."""
    game_id = _advance_to_bidding(service, state)
    service.place_bid(game_id, "E", 250)
    for player_id in ("S", "W", "N"):
        service.place_bid(game_id, player_id, None)
    service.name_trump(game_id, "E", Suit.SPADES)
    return game_id


def _complete_exchange(service: GameService, game_id: str, round_state: Round) -> None:
    """Pass four cards each way between the auction winner and their partner."""
    for player_id in ("E", "W"):
        service.pass_cards(game_id, player_id, list(round_state.hand(player_id))[:4])


def test_completed_exchange_reaches_trick_play():
    """The meld hold must end and hand the lead to the auction winner.

    With the immediate scheduler the meld display collapses to zero, so the
    round arrives in PLAYING as soon as the second pass lands.
    """
    service, state = make_service()
    game_id = _advance_to_passing(service, state)
    round_state = state.load(game_id).current_round
    _complete_exchange(service, game_id, round_state)
    assert round_state.phase == RoundPhase.PLAYING
    assert round_state.play_card("E", list(round_state.hand("E"))[0]) is None


def test_meld_reaches_scoring_after_hands_are_emptied():
    """Team meld totals must not collapse to zero once trick play is over."""
    service, state = make_service()
    game_id = _advance_to_passing(service, state)
    game = state.load(game_id)
    round_state = game.current_round
    _complete_exchange(service, game_id, round_state)

    expected = GameService._meld_scores(game, round_state)
    for player_id in ("N", "E", "S", "W"):
        hand = round_state.hand(player_id)
        hand.remove_many(list(hand))

    assert GameService._meld_scores(game, round_state) == expected


def test_resolve_draw_unique_winner():
    """The highest unique dealer-selection draw should win."""
    from pinochle.domain.cards.card import Card
    from pinochle.domain.cards.rank import Rank
    draws = {
        "N": Card(Rank.ACE, Suit.SPADES),
        "E": Card(Rank.KING, Suit.HEARTS),
        "S": Card(Rank.TEN, Suit.CLUBS),
        "W": Card(Rank.NINE, Suit.DIAMONDS),
    }
    assert GameService._resolve_draw(draws) == "N"


def test_resolve_draw_tie_returns_none():
    """Dealer-selection ties should return ``None`` and force a redraw."""
    from pinochle.domain.cards.card import Card
    from pinochle.domain.cards.rank import Rank
    draws = {
        "N": Card(Rank.ACE, Suit.SPADES),
        "E": Card(Rank.ACE, Suit.HEARTS),
        "S": Card(Rank.TEN, Suit.CLUBS),
        "W": Card(Rank.NINE, Suit.DIAMONDS),
    }
    assert GameService._resolve_draw(draws) is None
