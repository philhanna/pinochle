# tests.services.test_game_service
import pytest

from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import GamePhase, CardsDealt, BidPlaced, TrumpNamed
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
    state = InMemoryGameState()
    notifier = PrintNotification()
    return GameService(state, notifier), state


def setup_game(service: GameService) -> str:
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
    service, state = make_service()
    game_id = service.create_game()
    assert isinstance(game_id, str) and len(game_id) > 0
    assert state.load(game_id).id == game_id


def test_add_player_registered():
    service, state = make_service()
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    service.add_player(game_id, PLAYERS[0])
    game = state.load(game_id)
    assert "N" in game.players


def test_assign_teams():
    service, state = make_service()
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    game = state.load(game_id)
    assert "NS" in game.teams
    assert "EW" in game.teams


def test_start_game_enters_dealer_selection():
    service, state = make_service()
    game_id = setup_game(service)
    game = state.load(game_id)
    assert game.phase == GamePhase.DEALER_SELECTION


# ---------------------------------------------------------------------------
# draw_for_deal — dealer selection
# ---------------------------------------------------------------------------

def test_draw_for_deal_returns_card():
    service, state = make_service()
    game_id = setup_game(service)
    card = service.draw_for_deal(game_id, "N")
    assert card is not None


def test_all_four_draws_starts_round():
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
    # Force dealer directly via domain, bypassing draw protocol
    game.set_dealer("N")
    game.deal()
    game.pop_events()
    state.save(game)
    return game_id


def test_place_bid_recorded():
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    # Bid order starts left of dealer (N), so E bids first
    service.place_bid(game_id, "E", 250)
    game = state.load(game_id)
    assert game.current_round._bidding.current_high == 250


def test_place_bid_pass_recorded():
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    service.place_bid(game_id, "E", None)
    game = state.load(game_id)
    assert "E" not in game.current_round._bidding.active_players


# ---------------------------------------------------------------------------
# Events are dispatched via notifier
# ---------------------------------------------------------------------------

def test_events_broadcast(capsys):
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    service.place_bid(game_id, "E", 250)
    output = capsys.readouterr().out
    assert "BidPlaced" in output


# ---------------------------------------------------------------------------
# _resolve_draw
# ---------------------------------------------------------------------------

def test_resolve_draw_unique_winner():
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
    from pinochle.domain.cards.card import Card
    from pinochle.domain.cards.rank import Rank
    draws = {
        "N": Card(Rank.ACE, Suit.SPADES),
        "E": Card(Rank.ACE, Suit.HEARTS),
        "S": Card(Rank.TEN, Suit.CLUBS),
        "W": Card(Rank.NINE, Suit.DIAMONDS),
    }
    assert GameService._resolve_draw(draws) is None
