# pinochle.app
"""Application bootstrap.

Wires ports to their concrete adapters and exposes factory functions
for building the object graph.  No game logic lives here.
"""
from pinochle.adapters.in_memory_game_state import InMemoryGameState
from pinochle.adapters.print_notification import PrintNotification
from pinochle.adapters.svg_card_image import SvgCardImage
from pinochle.strategies.computer_player_strategy import ComputerPlayerStrategy
from pinochle.ports.card_image_port import CardImagePort
from pinochle.services.game_service import GameService


def create_default_app() -> dict:
    """Return the default wired-up application components.

    Returns a dict with keys:
        service      – GameService (implements AdminPort + PlayerActionPort)
        card_images  – CardImagePort implementation
        computer     – ComputerPlayerAdapter (AI decision helpers)
    """
    game_state = InMemoryGameState()
    notifier = PrintNotification()
    card_images: CardImagePort = SvgCardImage()
    service = GameService(game_state, notifier)
    computer = ComputerPlayerStrategy()

    return {
        "service": service,
        "card_images": card_images,
        "computer": computer,
    }
