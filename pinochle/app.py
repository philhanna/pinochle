# pinochle.app
"""Application bootstrap.

Wires ports to their concrete adapters and exposes factory functions
for building the object graph.  No game logic lives here.
"""
from pinochle.adapters.outbound.in_memory_game_state import InMemoryGameState
from pinochle.adapters.outbound.print_notification import PrintNotification
from pinochle.adapters.outbound.svg_card_image import SvgCardImage
from pinochle.adapters.inbound.computer_player_adapter import ComputerPlayerAdapter
from pinochle.ports.outbound.game_state_port import GameStatePort
from pinochle.ports.outbound.notification_port import NotificationPort
from pinochle.ports.outbound.card_image_port import CardImagePort


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
