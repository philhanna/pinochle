# pinochle.services.game_service
import uuid

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import (
    BidPlaced,
    CardsDealt,
    DealerSelected,
    Game,
    GamePhase,
    GameOver,
    RoundScored,
    TrickCompleted,
    TrumpNamed,
)
from pinochle.domain.meld import total_meld
from pinochle.domain.player import Player
from pinochle.domain.scoring import WINNING_SCORE, resolve_round, score_tricks
from pinochle.domain.team import Team
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.services.round import Round, RoundPhase

_NS = "NS"
_EW = "EW"


class GameService(AdminPort, PlayerActionPort):
    """Application service — the use-case layer.

    Implements both AdminPort and PlayerActionPort. Every method follows
    the same pattern:
        1. Load game state.
        2. Execute use-case orchestration.
        3. Drain and broadcast all pending events.
        4. Save updated game state.

    Dealer selection state (drawn cards) is tracked here because it is
    transient application-flow logic rather than persisted domain state.
    """

    def __init__(self, state: GameStatePort, notifier: NotificationPort):
        self._state = state
        self._notifier = notifier
        self._pending_draws: dict[str, dict[str, Card]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(self, game: Game) -> None:
        for event in game.pop_events():
            self._notifier.broadcast(game.id, event)

    def _load_save(self, game_id: str, fn) -> None:
        game = self._state.load(game_id)
        fn(game)
        self._dispatch(game)
        self._state.save(game)

    def _start_round(self, game: Game) -> None:
        round_state = Round(
            dealer_id=game.dealer_id,
            player_order=game.player_order,
        )
        round_state.deal()
        game.begin_round(round_state)

        for pid in game.player_order:
            game.emit(CardsDealt(
                game_id=game.id,
                player_id=pid,
                cards=list(round_state.hand(pid)),
            ))

    @staticmethod
    def _player_team_map(game: Game) -> dict[str, str]:
        return {pid: game.team_id_for_player(pid) for pid in game.players}

    @staticmethod
    def _meld_scores(game: Game, round_state: Round) -> dict[str, int]:
        totals: dict[str, int] = {}
        for pid in game.players:
            team_id = game.team_id_for_player(pid)
            totals[team_id] = totals.get(team_id, 0) + total_meld(
                list(round_state.hand(pid)),
                round_state.trump,
            )
        return totals

    @staticmethod
    def _check_winner(game: Game, bid_winner: str | None) -> str | None:
        over = [team for team in game.teams.values() if team.cumulative_score >= WINNING_SCORE]
        if not over:
            return None
        if len(over) > 1:
            return bid_winner and game.team_id_for_player(bid_winner)
        return over[0].id

    def _score_round(self, game: Game) -> None:
        round_state = game.current_round
        player_team = self._player_team_map(game)
        tricks = round_state.tricks
        last_winner = tricks[-1].winner()

        trick_scores = score_tricks(tricks, last_winner, player_team)
        meld_scores = self._meld_scores(game, round_state)
        bid_team_id = game.team_id_for_player(round_state.bid_winner)
        net = resolve_round(trick_scores, meld_scores, bid_team_id, round_state.contract)

        for team_id, points in net.items():
            game.add_score(team_id, points)

        ns_score = game.teams.get(_NS, Team(_NS, "N/S")).cumulative_score
        ew_score = game.teams.get(_EW, Team(_EW, "E/W")).cumulative_score
        game.emit(RoundScored(game_id=game.id, ns_score=ns_score, ew_score=ew_score))

        winner = self._check_winner(game, round_state.bid_winner)
        if winner:
            game.set_finished()
            game.emit(GameOver(game_id=game.id, winning_team_id=winner))
            return

        game.phase = GamePhase.DEALER_SELECTION
        game.set_dealer(game.next_dealer())
        self._start_round(game)

    # ------------------------------------------------------------------
    # AdminPort
    # ------------------------------------------------------------------

    def create_game(self) -> str:
        game_id = str(uuid.uuid4())
        game = Game(game_id)
        self._state.save(game)
        return game_id

    def add_player(self, game_id: str, player: Player) -> None:
        self._load_save(game_id, lambda g: g.add_player(player))

    def assign_teams(self, game_id: str, ns: Team, ew: Team) -> None:
        def _assign(g: Game) -> None:
            g.add_team(ns)
            g.add_team(ew)

        self._load_save(game_id, _assign)

    def start_game(self, game_id: str) -> None:
        self._load_save(game_id, lambda g: g.start_dealer_selection())
        self._pending_draws[game_id] = {}

    # ------------------------------------------------------------------
    # PlayerActionPort
    # ------------------------------------------------------------------

    def draw_for_deal(self, game_id: str, player_id: str) -> Card:
        deck = Deck()
        deck.shuffle()
        card = deck.deal(1)[0]

        draws = self._pending_draws.setdefault(game_id, {})
        draws[player_id] = card

        game = self._state.load(game_id)
        if len(draws) == len(game.players):
            winner = self._resolve_draw(draws)
            if winner:
                self._pending_draws.pop(game_id, None)

                def _set_dealer_and_deal(g: Game) -> None:
                    g.set_dealer(winner)
                    g.emit(DealerSelected(game_id=g.id, dealer_player_id=winner))
                    self._start_round(g)

                self._load_save(game_id, _set_dealer_and_deal)
            else:
                self._pending_draws[game_id] = {}

        return card

    @staticmethod
    def _resolve_draw(draws: dict[str, Card]) -> str | None:
        max_value = max(c.rank.value for c in draws.values())
        winners = [pid for pid, c in draws.items() if c.rank.value == max_value]
        return winners[0] if len(winners) == 1 else None

    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        def _place_bid(g: Game) -> None:
            g.current_round.place_bid(player_id, amount)
            g.emit(BidPlaced(game_id=g.id, player_id=player_id, amount=amount))

        self._load_save(game_id, _place_bid)

    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        def _name_trump(g: Game) -> None:
            g.current_round.name_trump(player_id, suit)
            g.emit(TrumpNamed(game_id=g.id, suit=suit))

        self._load_save(game_id, _name_trump)

    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        self._load_save(game_id, lambda g: g.current_round.pass_cards(player_id, cards))

    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        def _play_card(g: Game) -> None:
            winner_id = g.current_round.play_card(player_id, card)
            if winner_id is None:
                return

            last_trick = g.current_round.tricks[-1]
            g.emit(TrickCompleted(
                game_id=g.id,
                winner_player_id=winner_id,
                cards_played=last_trick.cards,
            ))
            if g.current_round.phase == RoundPhase.SCORING:
                self._score_round(g)

        self._load_save(game_id, _play_card)
