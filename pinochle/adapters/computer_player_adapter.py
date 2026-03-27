# pinochle.adapters.computer_player_adapter
from pinochle.domain.cards.card import Card
from pinochle.domain.cards.suit import Suit
from pinochle.domain.game import Game
from pinochle.ports.player_action_port import PlayerActionPort
from pinochle.ports.game_state_port import GameStatePort


class ComputerPlayerAdapter(PlayerActionPort):
    """Rule-based computer player.

    Strategy:
    - Bidding: bid the minimum if hand looks reasonable, otherwise pass.
    - Trump: pick the suit with the most cards in hand.
    - Passing: give the partner the four lowest-ranked cards.
    - Playing: always play the highest legal card.
    """

    def __init__(self, state: GameStatePort):
        self._state = state

    def draw_for_deal(self, game_id: str, player_id: str) -> Card:
        from pinochle.domain.cards.deck import Deck
        deck = Deck()
        deck.shuffle()
        return deck.deal(1)[0]

    def place_bid(self, game_id: str, player_id: str, amount: int | None) -> None:
        game = self._state.load(game_id)
        game.place_bid(player_id, amount)
        self._state.save(game)

    def name_trump(self, game_id: str, player_id: str, suit: Suit) -> None:
        game = self._state.load(game_id)
        game.name_trump(player_id, suit)
        self._state.save(game)

    def pass_cards(self, game_id: str, player_id: str, cards: list[Card]) -> None:
        game = self._state.load(game_id)
        game.pass_cards(player_id, cards)
        self._state.save(game)

    def play_card(self, game_id: str, player_id: str, card: Card) -> None:
        game = self._state.load(game_id)
        game.play_card(player_id, card)
        self._state.save(game)

    # ------------------------------------------------------------------
    # Decision helpers (stateless — take the hand as input)
    # ------------------------------------------------------------------

    @staticmethod
    def choose_trump(hand_cards: list[Card]) -> Suit:
        """Pick the suit with the most cards; break ties by suit order."""
        counts = {suit: sum(1 for c in hand_cards if c.suit == suit) for suit in Suit}
        return max(counts, key=lambda s: counts[s])

    @staticmethod
    def choose_cards_to_pass(hand_cards: list[Card], count: int = 4) -> list[Card]:
        """Return the `count` lowest-ranked cards to pass to partner."""
        sorted_cards = sorted(hand_cards, key=lambda c: c.rank.value)
        return sorted_cards[:count]

    @staticmethod
    def choose_play(legal_cards: list[Card]) -> Card:
        """Return the highest-ranked card among the legal options."""
        return max(legal_cards, key=lambda c: c.rank.value)
