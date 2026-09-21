# tests.services.test_game_events
import random

import pytest

from pinochle.adapters.immediate_scheduler import ImmediateScheduler
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.rank import Rank
from pinochle.domain.cards.suit import Suit
from pinochle.domain.meld import MeldUnit
from pinochle.domain.game import (
    CardPlayed,
    CardsDealt,
    ContractOffered,
    DealerSelectionStarted,
    DrawMade,
    DrawTied,
    GameConfigured,
    GameEvent,
    GameOver,
    HoldEnded,
    PlayBegun,
    RoundScored,
    RoundStarted,
    TrickCleared,
    TrickCompleted,
    TurnPrompt,
)
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.scoring import WINNING_SCORE
from pinochle.domain.team import Team
from pinochle.ports.notification_port import NotificationPort
from pinochle.services.game_service import GameService
from pinochle.services.round import RoundPhase

PLAYERS = [
    Player("N", "North", PlayerType.HUMAN, Position.NORTH),
    Player("E", "East", PlayerType.HUMAN, Position.EAST),
    Player("S", "South", PlayerType.HUMAN, Position.SOUTH),
    Player("W", "West", PlayerType.HUMAN, Position.WEST),
]


class RecordingNotification(NotificationPort):
    """``NotificationPort`` double that keeps every event in publication order."""

    def __init__(self):
        """Start with an empty log."""
        self.events: list[GameEvent] = []

    def notify(self, player_id: str, event: GameEvent) -> None:
        """Record a single-player delivery."""
        self.events.append(event)

    def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Record a delivery to every player in the game."""
        self.events.append(event)

    def of_type(self, event_type) -> list[GameEvent]:
        """Return every recorded event of ``event_type``, in order."""
        return [e for e in self.events if isinstance(e, event_type)]

    def names(self) -> list[str]:
        """Return the recorded event type names, in order."""
        return [type(e).__name__ for e in self.events]


@pytest.fixture
def table():
    """Return a service, its state store, and its recording notifier."""
    random.seed(7)
    state = InMemoryGameState()
    notifier = RecordingNotification()
    return GameService(state, notifier, ImmediateScheduler()), state, notifier


def start(service: GameService) -> str:
    """Create a fully seated game and enter dealer selection."""
    game_id = service.create_game()
    service.assign_teams(game_id, Team("NS", "Us"), Team("EW", "Them"))
    for player in PLAYERS:
        service.add_player(game_id, player)
    service.start_game(game_id)
    return game_id


def deal(service: GameService, state: InMemoryGameState) -> str:
    """Take a game through dealer selection so that a round has been dealt."""
    game_id = start(service)
    for position, player_id in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, player_id, position)
    while state.load(game_id).current_round is None:
        taken = service.positions_taken(game_id)
        free = (i for i in range(service.spread_size(game_id)) if i not in taken)
        for player_id in ["N", "E", "S", "W"]:
            service.draw_for_deal(game_id, player_id, next(free))
    return game_id


def win_auction(service: GameService, state: InMemoryGameState) -> tuple[str, str]:
    """Deal a round and let the first bidder take the contract at 250."""
    game_id = deal(service, state)
    round_state = state.load(game_id).current_round
    winner = round_state.current_player
    service.place_bid(game_id, winner, 250)
    for _ in range(3):
        service.place_bid(game_id, round_state.current_player, None)
    service.confirm_contract(game_id, winner, accept=True)
    service.name_trump(game_id, winner, Suit.SPADES)
    return game_id, winner


def expose_meld(service: GameService, state: InMemoryGameState) -> tuple[str, str]:
    """Take a round as far as the exposed meld, with the pass complete."""
    game_id, winner = win_auction(service, state)
    round_state = state.load(game_id).current_round
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        service.pass_cards(game_id, passer, list(round_state.hand(passer))[:4])
    return game_id, winner


def play_out(service: GameService, state: InMemoryGameState, game_id: str) -> None:
    """Play every remaining trick, always choosing the first legal card."""
    round_state = state.load(game_id).current_round
    while round_state is not None and round_state.phase == RoundPhase.PLAYING:
        player_id = round_state.current_player
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])
        round_state = state.load(game_id).current_round


# ---------------------------------------------------------------------------
# Setup and dealer selection
# ---------------------------------------------------------------------------

def test_starting_a_game_announces_the_table(table):
    """A client cannot draw the table without the seats, names, and teams."""
    service, _, notifier = table
    start(service)
    configured = notifier.of_type(GameConfigured)[0]
    assert [p.id for p in configured.players] == ["N", "E", "S", "W"]
    assert sorted(t.id for t in configured.teams) == ["EW", "NS"]
    assert configured.winning_score == WINNING_SCORE


def test_starting_a_game_announces_the_spread(table):
    """The spread's size is published so the client can lay out the positions."""
    service, _, notifier = table
    start(service)
    assert notifier.of_type(DealerSelectionStarted)[0].spread_size == 48


def test_each_draw_is_revealed_to_the_whole_table(table):
    """FR-15: every drawn card is revealed to all four players."""
    service, _, notifier = table
    game_id = start(service)
    card = service.draw_for_deal(game_id, "N", 5)
    drawn = notifier.of_type(DrawMade)
    assert len(drawn) == 1
    assert (drawn[0].player_id, drawn[0].position, drawn[0].card) == ("N", 5, card)


def test_a_tied_draw_is_announced_with_a_fresh_spread(table):
    """FR-14: a tie is public, and is followed by a whole new spread."""
    service, _, notifier = table
    game_id = start(service)
    cards = service._spreads[game_id].cards
    cards[0] = Card(Rank.ACE, Suit.SPADES)
    cards[1] = Card(Rank.ACE, Suit.HEARTS)
    cards[2] = Card(Rank.NINE, Suit.CLUBS)
    cards[3] = Card(Rank.NINE, Suit.DIAMONDS)
    for position, player_id in enumerate(["N", "E", "S", "W"]):
        service.draw_for_deal(game_id, player_id, position)

    tied = notifier.of_type(DrawTied)
    assert len(tied) == 1
    assert tied[0].cards["N"] == Card(Rank.ACE, Suit.SPADES)
    assert notifier.names()[-1] == "DealerSelectionStarted"


# ---------------------------------------------------------------------------
# Rounds
# ---------------------------------------------------------------------------

def test_round_started_precedes_the_hands(table):
    """A client resets the table on ``RoundStarted``, before the deal arrives."""
    service, state, notifier = table
    deal(service, state)
    names = notifier.names()
    assert names.index("RoundStarted") < names.index("CardsDealt")
    started = notifier.of_type(RoundStarted)[0]
    assert started.round_number == 1
    assert started.dealer_player_id == state.load(started.game_id).dealer_id


def test_the_table_holds_on_the_round_summary(table):
    """RT-13: the next deal waits on a seat, not on a clock."""
    service, state, notifier = table
    game_id, _ = expose_meld(service, state)
    service.begin_play(game_id, state.load(game_id).current_round.bid_winner)
    play_out(service, state, game_id)

    hold = state.load(game_id).current_hold
    assert hold is not None and hold.ackable
    assert hold.seconds is None, "RT-13 gives a hold awaiting a player no interval"
    assert [e.round_number for e in notifier.of_type(RoundStarted)] == [1]


def test_round_number_counts_up(table):
    """The second round dealt is round two, once a seat moves the table on."""
    service, state, notifier = table
    game_id, _ = expose_meld(service, state)
    service.begin_play(game_id, state.load(game_id).current_round.bid_winner)
    play_out(service, state, game_id)
    service.acknowledge(game_id, "N", state.load(game_id).current_hold.id)
    assert [e.round_number for e in notifier.of_type(RoundStarted)] == [1, 2]


def test_any_seat_may_move_the_table_on(table):
    """RT-13: not only the seat the summary is about, and not the administrator."""
    service, state, _ = table
    game_id, _ = expose_meld(service, state)
    service.begin_play(game_id, state.load(game_id).current_round.bid_winner)
    play_out(service, state, game_id)

    # "W" is picked blind: whoever won the auction, some other seat releases.
    service.acknowledge(game_id, "W", state.load(game_id).current_hold.id)
    assert state.load(game_id).current_hold is None


def test_releasing_a_hold_twice_changes_nothing(table):
    """RT-13: a second click, or a second player's, is expected and harmless."""
    service, state, notifier = table
    game_id, _ = expose_meld(service, state)
    service.begin_play(game_id, state.load(game_id).current_round.bid_winner)
    play_out(service, state, game_id)

    hold_id = state.load(game_id).current_hold.id
    service.acknowledge(game_id, "N", hold_id)
    service.acknowledge(game_id, "S", hold_id)

    assert len(notifier.of_type(HoldEnded)) == 1
    assert [e.round_number for e in notifier.of_type(RoundStarted)] == [1, 2]


def test_a_stale_hold_id_releases_nothing(table):
    """A click that arrived late must not release whatever hold came next."""
    service, state, notifier = table
    game_id, _ = expose_meld(service, state)
    service.begin_play(game_id, state.load(game_id).current_round.bid_winner)
    play_out(service, state, game_id)

    service.acknowledge(game_id, "N", state.load(game_id).current_hold.id + 99)
    assert state.load(game_id).current_hold is not None
    assert notifier.of_type(HoldEnded) == []



def test_a_lone_bidders_offer_is_public(table):
    """FR-32: the other three learn why the auction has paused."""
    service, state, notifier = table
    game_id = deal(service, state)
    round_state = state.load(game_id).current_round
    bidder = round_state.current_player
    service.place_bid(game_id, bidder, 250)
    for _ in range(3):
        service.place_bid(game_id, round_state.current_player, None)

    offered = notifier.of_type(ContractOffered)
    assert len(offered) == 1
    assert (offered[0].player_id, offered[0].amount) == (bidder, 250)


def test_inheriting_the_auction_is_not_a_lone_bid(table):
    """FR-32: a player who was outbid and inherits it gets no such offer."""
    service, state, notifier = table
    game_id = deal(service, state)
    round_state = state.load(game_id).current_round
    opener = round_state.current_player
    service.place_bid(game_id, opener, 250)
    raiser = round_state.current_player
    service.place_bid(game_id, raiser, 260)
    while round_state.phase == RoundPhase.BIDDING:
        service.place_bid(game_id, round_state.current_player, None)

    assert round_state.phase == RoundPhase.TRUMP
    assert round_state.bid_winner == raiser
    assert notifier.of_type(ContractOffered) == []


# ---------------------------------------------------------------------------
# turn_prompt
# ---------------------------------------------------------------------------

def test_turn_prompt_is_sent_only_to_the_seat_on_the_clock(table):
    """UI-9: the prompt is private, and regenerated for the new current player."""
    service, state, notifier = table
    game_id = deal(service, state)
    round_state = state.load(game_id).current_round
    opener = round_state.current_player

    prompts = notifier.of_type(TurnPrompt)
    assert len(prompts) == 1
    assert prompts[0].player_id == opener
    assert prompts[0].phase == "BIDDING"
    assert prompts[0].options == {"minimum_bid": 250, "may_pass": True}
    assert ("N", "E", "S", "W").count(opener) == 1  # sanity: exactly one seat


def test_turn_prompt_raises_the_minimum_bid_after_a_bid(table):
    """A subsequent prompt reflects the new high bid, not the opening one."""
    service, state, notifier = table
    game_id = deal(service, state)
    round_state = state.load(game_id).current_round
    opener = round_state.current_player
    service.place_bid(game_id, opener, 250)

    prompts = notifier.of_type(TurnPrompt)
    assert prompts[-1].options["minimum_bid"] == 260


def test_turn_prompt_carries_legal_plays_while_playing(table):
    """UI-9, FR-53: the highlighted set and the legal set are the same computation."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    round_state = state.load(game_id).current_round

    prompt = notifier.of_type(TurnPrompt)[-1]
    assert prompt.player_id == winner
    assert prompt.phase == "PLAYING"
    assert prompt.options["legal_plays"] == round_state.legal_plays(winner)


def test_no_turn_prompt_during_dealer_selection(table):
    """Dealer selection has no single acting seat, so nothing is prompted."""
    service, state, notifier = table
    start(service)
    assert notifier.of_type(TurnPrompt) == []


# ---------------------------------------------------------------------------
# Trick play
# ---------------------------------------------------------------------------

def test_play_begun_ends_the_meld_display(table):
    """FR-50a: the auction winner's word clears the meld from every client."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    begun = notifier.of_type(PlayBegun)
    assert len(begun) == 1
    assert begun[0].leader_player_id == winner


def test_every_card_is_announced_as_it_is_played(table):
    """FR-57: all four cards are visible before the trick completes."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    round_state = state.load(game_id).current_round
    for _ in range(4):
        player_id = round_state.current_player
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])

    played = notifier.of_type(CardPlayed)
    assert len(played) == 4
    assert played[0].player_id == winner
    names = notifier.names()
    assert names.index("TrickCompleted") > names.index("CardPlayed")


def test_trick_cleared_closes_the_pause_and_names_the_next_leader(table):
    """UI-15, RT-10: the sweep is an event, and the winner leads next (FR-56)."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    round_state = state.load(game_id).current_round
    for _ in range(4):
        player_id = round_state.current_player
        service.play_card(game_id, player_id, round_state.legal_plays(player_id)[0])

    completed = notifier.of_type(TrickCompleted)[0]
    cleared = notifier.of_type(TrickCleared)[0]
    assert cleared.winner_player_id == completed.winner_player_id
    assert cleared.next_leader_player_id == completed.winner_player_id
    assert notifier.names().index("TrickCleared") > notifier.names().index("TrickCompleted")


def test_the_last_trick_cleared_has_no_next_leader(table):
    """Nobody leads after the twelfth trick; the round is over."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    play_out(service, state, game_id)

    cleared = notifier.of_type(TrickCleared)
    assert len(cleared) == 12
    assert all(c.next_leader_player_id == c.winner_player_id for c in cleared[:11])
    assert cleared[-1].next_leader_player_id is None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def test_round_scored_reports_the_whole_breakdown(table):
    """FR-66: meld, card points, bonus, round total, and cumulative, per team."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    play_out(service, state, game_id)

    scored = notifier.of_type(RoundScored)[0]
    lines = {line.team_id: line for line in scored.teams}
    assert sorted(lines) == ["EW", "NS"]
    assert sum(line.card_points for line in scored.teams) == 240   # FR-59
    assert sum(line.last_trick_bonus for line in scored.teams) == 10  # FR-60
    for line in scored.teams:
        assert line.round_total == line.meld + line.card_points + line.last_trick_bonus
        assert line.cumulative_score == line.points_applied  # first round
    assert scored.round_number == 1
    assert scored.contract == 250
    assert not scored.tossed_in


def test_a_set_team_loses_the_contract_and_its_meld(table):
    """FR-63, and FR-66's requirement to say which way it went."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    service.begin_play(game_id, winner)
    play_out(service, state, game_id)

    scored = notifier.of_type(RoundScored)[0]
    bid_line = next(l for l in scored.teams if l.team_id == scored.bid_team_id)
    if scored.made_contract:
        assert bid_line.round_total >= scored.contract
        assert bid_line.points_applied == bid_line.round_total
    else:
        assert bid_line.round_total < scored.contract
        assert bid_line.points_applied == -(scored.contract + bid_line.meld)


def test_a_made_contract_is_added_in_full(table):
    """FR-62: a bidding team that meets the contract banks its round total.

    The recorded meld is inflated so that the contract is certainly made,
    since a round played by always choosing the first legal card is not
    otherwise a reliable way to reach 250.
    """
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    round_state = state.load(game_id).current_round
    round_state._meld[winner] = [MeldUnit("Test meld", 500)]
    service.begin_play(game_id, winner)
    play_out(service, state, game_id)

    scored = notifier.of_type(RoundScored)[0]
    bid_line = next(l for l in scored.teams if l.team_id == scored.bid_team_id)
    assert scored.made_contract
    assert bid_line.meld >= 500
    assert bid_line.round_total >= scored.contract
    assert bid_line.points_applied == bid_line.round_total
    assert bid_line.cumulative_score == bid_line.round_total


def test_a_tossed_in_contract_scores_no_tricks(table):
    """FR-50c: the bidder loses the contract, the opponents keep their meld."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    game = state.load(game_id)
    bid_team = game.team_id_for_player(winner)
    service.toss_in(game_id, winner)

    scored = notifier.of_type(RoundScored)[0]
    assert scored.tossed_in
    assert not scored.made_contract
    for line in scored.teams:
        assert line.card_points == 0
        assert line.last_trick_bonus == 0
        assert line.round_total == line.meld
        if line.team_id == bid_team:
            assert line.points_applied == -scored.contract
        else:
            assert line.points_applied == line.meld


def test_game_over_carries_the_final_scores(table):
    """FR-71: the result is announced with both cumulative totals."""
    service, state, notifier = table
    game_id, winner = expose_meld(service, state)
    game = state.load(game_id)
    idle_team = "NS" if game.team_id_for_player(winner) == "EW" else "EW"
    game.add_score(idle_team, WINNING_SCORE)
    service.toss_in(game_id, winner)

    over = notifier.of_type(GameOver)
    assert len(over) == 1
    assert over[0].winning_team_id == idle_team
    scores = {"NS": over[0].ns_score, "EW": over[0].ew_score}
    assert scores[idle_team] >= WINNING_SCORE
