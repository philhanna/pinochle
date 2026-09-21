# tests.services.test_game_service
import pytest

from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.adapters.immediate_scheduler import ImmediateScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.errors import (
    IllegalActionError,
    UnknownGameError,
    WrongPhaseError,
)
from pinochle.domain.game import GamePhase
from pinochle.services.round import Round, RoundPhase
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import Team
from pinochle.services.game_service import TRICK_CLEAR_SECONDS, GameService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEAMS = [
    Team("NS", "North-South"),
    Team("EW", "East-West"),
]

PLAYERS = [
    Player("N", "North", PlayerType.HUMAN, Position.NORTH),
    Player("E", "East",  PlayerType.HUMAN, Position.EAST),
    Player("S", "South", PlayerType.HUMAN, Position.SOUTH),
    Player("W", "West",  PlayerType.HUMAN, Position.WEST),
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


def test_assign_teams_rejects_configurable_ids():
    """Team ids are fixed by the seating and may not be renamed."""
    service, _ = make_service()
    game_id = service.create_game()
    with pytest.raises(IllegalActionError):
        service.assign_teams(game_id, Team("US", "Us"), Team("THEM", "Them"))


def test_note_seat_thinking_broadcasts_without_a_turn_prompt(capsys):
    """RT-7/RT-10: seat_thinking goes out; no redundant turn_prompt follows it."""
    service, state = make_service()
    game_id = _advance_to_bidding(service, state)
    capsys.readouterr()

    service.note_seat_thinking(game_id, "E")

    output = capsys.readouterr().out
    assert "SeatThinking" in output
    assert "TurnPrompt" not in output


def test_abandon_game_marks_it_finished():
    """RT-12: an abandoned game must not accept further play."""
    service, state = make_service()
    game_id = setup_game(service)
    service.abandon_game(game_id)
    assert state.load(game_id).phase == GamePhase.FINISHED


def test_start_game_enters_dealer_selection():
    """Starting a fully configured game should enter dealer selection."""
    service, state = make_service()
    game_id = setup_game(service)
    game = state.load(game_id)
    assert game.phase == GamePhase.DEALER_SELECTION


# ---------------------------------------------------------------------------
# draw_for_deal — dealer selection
# ---------------------------------------------------------------------------

def test_draw_for_deal_returns_the_card_at_that_position():
    """Drawing returns whichever card lies at the chosen spread position."""
    service, state = make_service()
    game_id = setup_game(service)
    expected = service._spreads[game_id].cards[7]
    assert service.draw_for_deal(game_id, "N", 7) == expected


def test_all_four_draws_starts_round():
    """Four dealer-selection draws should resolve or trigger a redraw."""
    service, state = make_service()
    game_id = setup_game(service)
    for position, pid in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, pid, position)
    # After all four draw, game either re-draws (tie) or moves to IN_ROUND
    game = state.load(game_id)
    assert game.phase in (GamePhase.DEALER_SELECTION, GamePhase.IN_ROUND)


def test_a_position_cannot_be_taken_twice():
    """Two players may not draw the same physical card (FR-12)."""
    service, _ = make_service()
    game_id = setup_game(service)
    service.draw_for_deal(game_id, "N", 3)
    with pytest.raises(IllegalActionError):
        service.draw_for_deal(game_id, "E", 3)


def test_a_player_cannot_draw_twice():
    """Each player takes exactly one card from the spread."""
    service, _ = make_service()
    game_id = setup_game(service)
    service.draw_for_deal(game_id, "N", 0)
    with pytest.raises(IllegalActionError):
        service.draw_for_deal(game_id, "N", 1)


def test_position_outside_the_spread_is_rejected():
    """Only the 48 laid-out positions may be chosen."""
    service, _ = make_service()
    game_id = setup_game(service)
    assert service.spread_size(game_id) == 48
    with pytest.raises(IllegalActionError):
        service.draw_for_deal(game_id, "N", 48)


def test_a_draw_after_the_dealer_is_settled_is_refused():
    """NFR-4: a late draw is an out-of-phase action, not a crash.

    The spread is discarded once a dealer is settled, so there is nothing
    left to draw from. A tab that was showing the spread when the deal began
    — a stale one, or one that has just reconnected — must be refused like
    any other action submitted for the wrong phase.
    """
    service, state = make_service()
    game_id = setup_game(service)
    cards = service._spreads[game_id].cards
    # Distinct ranks, so the draw settles a dealer instead of tying (FR-14).
    for position, rank in enumerate([Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK]):
        cards[position] = Card(rank, Suit.SPADES)
    for position, pid in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, pid, position)
    assert state.load(game_id).phase == GamePhase.IN_ROUND

    with pytest.raises(WrongPhaseError):
        service.draw_for_deal(game_id, "N", 10)


def test_a_draw_before_the_game_starts_is_refused():
    """There is no spread until the game starts, and no draw either."""
    service, _ = make_service()
    game_id = service.create_game()
    service.assign_teams(game_id, TEAMS[0], TEAMS[1])
    for player in PLAYERS:
        service.add_player(game_id, player)

    with pytest.raises(WrongPhaseError):
        service.draw_for_deal(game_id, "N", 0)


def test_a_draw_for_an_unknown_game_is_reported_as_an_unknown_game():
    """A bad id must stay a 404, not be dressed up as the wrong phase."""
    service, _ = make_service()

    with pytest.raises(UnknownGameError):
        service.draw_for_deal("no-such-game", "N", 0)


def test_tie_lays_out_a_fresh_spread_for_all_four():
    """A tie on rank restarts the whole draw, not just for those tied."""
    service, state = make_service()
    game_id = setup_game(service)
    cards = service._spreads[game_id].cards
    cards[0] = Card(Rank.ACE, Suit.SPADES)
    cards[1] = Card(Rank.ACE, Suit.HEARTS)
    cards[2] = Card(Rank.NINE, Suit.CLUBS)
    cards[3] = Card(Rank.NINE, Suit.DIAMONDS)

    for position, pid in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, pid, position)

    assert state.load(game_id).dealer_id is None
    assert service.positions_taken(game_id) == set()


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
    service.confirm_contract(game_id, "E", accept=True)
    service.name_trump(game_id, "E", Suit.SPADES)
    return game_id


def _complete_exchange(service: GameService, game_id: str, round_state: Round) -> None:
    """Pass four cards each way between the auction winner and their partner."""
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        service.pass_cards(game_id, passer, list(round_state.hand(passer))[:4])


def test_completed_exchange_reaches_trick_play():
    """The meld display ends only after a seat clicks Continue."""
    service, state = make_service()
    game_id = _advance_to_passing(service, state)
    round_state = state.load(game_id).current_round
    _complete_exchange(service, game_id, round_state)
    assert round_state.phase == RoundPhase.MELDING
    with pytest.raises(WrongPhaseError, match="Continue"):
        service.begin_play(game_id, "E")
    service.acknowledge(game_id, "S", state.load(game_id).current_hold.id)
    assert round_state.phase == RoundPhase.PLAYING
    assert round_state.play_card("E", list(round_state.hand("E"))[0]) is None


def test_trick_clear_pause_rejects_a_new_lead_until_cleared(capsys):
    """RT-8/RT-9: a completed trick blocks play until the server clears it (ARC-10)."""
    state = InMemoryGameState()
    notifier = PrintNotification()
    scheduler = FakeScheduler()
    service = GameService(state, notifier, scheduler)

    game_id = _advance_to_passing(service, state)
    round_state = state.load(game_id).current_round
    _complete_exchange(service, game_id, round_state)
    service.acknowledge(game_id, "S", state.load(game_id).current_hold.id)

    for _ in range(4):
        player_id = round_state.current_player
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])

    assert round_state.trick_pending is True
    capsys.readouterr()  # discard everything printed so far
    with pytest.raises(WrongPhaseError):
        service.play_card(game_id, "N", list(round_state.hand("N"))[0])
    assert "TrickCleared" not in capsys.readouterr().out

    scheduler.advance(TRICK_CLEAR_SECONDS)
    assert round_state.trick_pending is False
    assert "TrickCleared" in capsys.readouterr().out


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


def _deal_via_dealer_selection(service: GameService, state: InMemoryGameState) -> str:
    """Seat a game and drive it through dealer selection into a dealt round."""
    game_id = setup_game(service)
    for position, pid in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, pid, position)
    while state.load(game_id).current_round is None:
        taken = service.positions_taken(game_id)
        free = (i for i in range(service.spread_size(game_id)) if i not in taken)
        for pid in ["N", "E", "S", "W"]:
            service.draw_for_deal(game_id, pid, next(free))
    return game_id


def test_seeded_rng_makes_the_deal_reproducible():
    """NFR-7: two services seeded alike deal identical hands."""
    from random import Random

    def make_seeded_service():
        state = InMemoryGameState()
        service = GameService(
            state, PrintNotification(), ImmediateScheduler(), rng=Random(7),
        )
        return service, state

    service_a, state_a = make_seeded_service()
    game_a = _deal_via_dealer_selection(service_a, state_a)

    service_b, state_b = make_seeded_service()
    game_b = _deal_via_dealer_selection(service_b, state_b)

    hand_a = state_a.load(game_a).current_round.hand("N")
    hand_b = state_b.load(game_b).current_round.hand("N")
    assert list(hand_a) == list(hand_b)


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
