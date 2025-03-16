import platform

def IS_WINDOWS():
    os_name = platform.system()
    return os_name == 'Windows'
    
from .rank import Rank
from .suit import Suit
from .card import Card

__all__ = [
    'IS_WINDOWS',
    'Rank',
    'Suit',
    'Card', 
]