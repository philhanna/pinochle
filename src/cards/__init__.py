import platform
from .rank import Rank
from .suit import Suit
from .card import Card

IS_WINDOWS = False
os_name = platform.system()
if os_name == 'Windows':
    IS_WINDOWS = True
    
__all__ = [
    'IS_WINDOWS',
    'Rank',
    'Suit',
    'Card', 
]