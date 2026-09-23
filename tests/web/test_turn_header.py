# tests.web.test_turn_header
from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.adapters.immediate_scheduler import ImmediateScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.domain.cards.suit import Suit
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import Team
from pinochle.services.game_service import GameService
from pinochle.services.round import RoundPhase
from pinochle.web.turn_header import build_turn_header

TEAMS = [Team("NS", "North-South"), Team("EW", "East-West")]
PLAYERS = [
    Player("N", "North", PlayerType.HUMAN, Position.NORTH),
    Player("E", "East", PlayerType.HUMAN, Position.EAST),
    Player("S", "South", PlayerType.HUMAN, Position.SOUTH),
    Player("W", "West", PlayerType.HUMAN, Position.WEST),
]


def setup_game() -> tuple[GameService, InMemoryGameState, str]:
    """Return a service, its state store, and a game seated but not started."""
    state = InMemoryGameState()
    service = GameService(state, PrintNotification(), ImmediateScheduler())
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    for player in PLAYERS:
        service.add_player(game_id, player)
    return service, state, game_id


def deal_a_round(service: GameService, state: InMemoryGameState, game_id: str):
    """Drive a game from setup through dealer selection into a dealt round."""
    service.start_game(game_id)
    for position, player_id in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, player_id, position)
    while state.load(game_id).current_round is None:
        hold = state.load(game_id).current_hold
        if hold is not None:
            service.acknowledge(game_id, "N", hold.id)
            continue
        taken = service.positions_taken(game_id)
        free = (i for i in range(service.spread_size(game_id)) if i not in taken)
        for player_id in ["N", "E", "S", "W"]:
            service.draw_for_deal(game_id, player_id, next(free))
    return state.load(game_id)


def test_setup_phase_has_no_current_player():
    """Before dealer selection, there is nothing for a client to act on."""
    _, state, game_id = setup_game()
    game = state.load(game_id)
    header = build_turn_header(game)
    assert header == {
        "phase": "SETUP",
        "current_player_id": None,
        "paused": None,
        "hold": None,
        "round_number": 0,
    }


def test_in_round_reports_the_round_phase_and_current_player():
    """Once a round is dealt, the header names the round phase and actor."""
    service, state, game_id = setup_game()
    game = deal_a_round(service, state, game_id)
    header = build_turn_header(game)
    assert header["phase"] == "BIDDING"
    assert header["current_player_id"] == game.current_round.current_player
    assert header["paused"] is None
    assert header["round_number"] == 1


def test_trick_clear_pause_is_reported():
    """RT-8: a completed, not-yet-cleared trick is a real reported pause."""
    state = InMemoryGameState()
    service = GameService(state, PrintNotification(), FakeScheduler())
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    for player in PLAYERS:
        service.add_player(game_id, player)
    game = deal_a_round(service, state, game_id)
    round_state = game.current_round

    winner = round_state.current_player
    service.place_bid(game_id, winner, 250)
    for _ in range(3):
        service.place_bid(game_id, round_state.current_player, None)
    service.confirm_contract(game_id, winner, accept=True)
    service.name_trump(game_id, winner, Suit.SPADES)
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        service.pass_cards(game_id, passer, list(round_state.hand(passer))[:4])
    service.acknowledge(game_id, winner, state.load(game_id).current_hold.id)

    for _ in range(4):
        player_id = round_state.current_player
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])

    header = build_turn_header(state.load(game_id))
    assert header["paused"] == "trick_clear"
    assert header["current_player_id"] is None


def test_thinking_seat_is_reported_when_no_other_pause_is_active():
    """Once the computer driver exists, its delay shows up the same way."""
    _, state, game_id = setup_game()
    game = state.load(game_id)
    header = build_turn_header(game, thinking_player_id="E")
    assert header["paused"] == "thinking"
