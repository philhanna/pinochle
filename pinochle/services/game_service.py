# pinochle.services.game_service
import uuid

from pinochle.domain.cards.card import Card
from pinochle.domain.cards.deck import Deck
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import Game
from pinochle.domain.player import Player
from pinochle.domain.team import Team
from pinochle.ports.admin_port import AdminPort
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.player_action_port import PlayerActionPort


class GameService(AdminPort, PlayerActionPort):
    """Application service — the use-case layer.

    Implements both AdminPort and PlayerActionPort.  Every method follows
    the same pattern:
        1. Load game state.
        2. Call the domain.
        3. Drain and broadcast all pending events.
        4. Save updated game state.

    Dealer selection state (drawn cards) is tracked here rather than in
    the domain, because it is transient application-flow logic.
    """

    def __init__(self, state: GameStatePort, notifier: NotificationPort):
        self._state = state
        self._notifier = notifier
        # game_id → {player_id → Card} — tracks draws during dealer selection
        self._pending_draws: dict[str, dict[str, Card]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dispatch(self, game: Game) -> None:
        """Drain domain events and broadcast each one."""
        for event in game.pop_events():
            self._notifier.broadcast(game.id, event)

    def _load_save(self, game_id: str, fn) -> None:
        game = self._state.load(game_id)
        fn(game)
        self._dispatch(game)
        self._state.save(game)

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
        """Draw one card for dealer selection.

        When all four players have drawn, the player holding the highest
        card is named dealer and the first round is dealt automatically.
        On a tie the draws are cleared and players must draw again.

        Returns the card that was drawn by this player.
        """
        deck = Deck()
        deck.shuffle()
        card = deck.deal(1)[0]

        draws = self._pending_draws.setdefault(game_id, {})
        draws[player_id] = card

        game = self._state.load(game_id)
        num_players = len(game.players)

        if len(draws) == num_players:
            winner = self._resolve_draw(draws)
            if winner:
                self._pending_draws.pop(game_id, None)

                def _set_dealer_and_deal(g: Game) -> None:
                    g.set_dealer(winner)
                    g.deal()

                self._load_save(game_id, _set_dealer_and_deal)
            else:
                # Tie — reset so players draw again
                self._pending_draws[game_id] = {}

        return card

    @staticmethod
    def _resolve_draw(draws: dict[str, Card]) -> str | None:
        """Return the player_id of the unique highest card, or None on tie."""
        max_value = max(c.rank.value for c in draws.values())
        winners = [pid for pid, c in draws.items() if c.rank.value == max_value]
        return winners[0] if len(winners) == 1 else None

    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        self._load_save(game_id, lambda g: g.place_bid(player_id, amount))

    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        self._load_save(game_id, lambda g: g.name_trump(player_id, suit))

    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        self._load_save(game_id, lambda g: g.pass_cards(player_id, cards))

    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        self._load_save(game_id, lambda g: g.play_card(player_id, card))
