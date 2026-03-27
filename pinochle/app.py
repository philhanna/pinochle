# pinochle.app
"""Application bootstrap.

Wires ports to their concrete adapters and exposes factory functions
for building the object graph.  No game logic lives here.
"""
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.adapters.computer_player_adapter import ComputerPlayerAdapter
from pinochle.ports.game_state_port import GameStatePort
from pinochle.ports.notification_port import NotificationPort
from pinochle.ports.card_image_port import CardImagePort


def create_default_app() -> dict:
    """Return the default wired-up application components.

    Returns a dict with keys:
        game_state   – GameStatePort implementation
        notifier     – NotificationPort implementation
        card_images  – CardImagePort implementation
        computer     – ComputerPlayerAdapter (inbound, for AI players)
    """
    game_state: GameStatePort = InMemoryGameState()
    notifier: NotificationPort = PrintNotification()
    card_images: CardImagePort = SvgCardImage()
    computer = ComputerPlayerAdapter(game_state)

    return {
        "game_state": game_state,
        "notifier": notifier,
        "card_images": card_images,
        "computer": computer,
    }
