# tests.adapters.test_in_memory_seat_tokens
from pinochle.adapters.in_memory_seat_tokens import InMemorySeatTokens
from tests.ports.test_seat_token_port import run_contract


def test_contract():
    """Verify the in-memory adapter satisfies the shared seat-token contract."""
    run_contract(InMemorySeatTokens())


def test_default_tokens_are_unguessable_and_unique():
    """Without an injected factory, minted tokens should be long and distinct."""
    tokens = InMemorySeatTokens()
    a = tokens.mint("g1", "N")
    b = tokens.mint("g1", "E")
    assert a != b
    assert len(a) >= 32 and len(b) >= 32


def test_injected_token_factory_is_used():
    """Tests can supply a deterministic factory instead of a random one."""
    counter = iter(["token-1", "token-2"])
    tokens = InMemorySeatTokens(token_factory=lambda: next(counter))
    assert tokens.mint("g1", "N") == "token-1"
    assert tokens.mint("g1", "E") == "token-2"


def test_two_games_do_not_share_tokens():
    """A token minted for one game must not resolve a seat in another."""
    tokens = InMemorySeatTokens()
    token = tokens.mint("g1", "N")
    tokens.mint("g2", "N")
    assert tokens.resolve("g2", token) is None


def test_revoking_one_game_leaves_others_untouched():
    """Revoking a finished game's tokens must not affect a different game."""
    tokens = InMemorySeatTokens()
    t1 = tokens.mint("g1", "N")
    t2 = tokens.mint("g2", "N")
    tokens.revoke_game("g1")
    assert tokens.resolve("g1", t1) is None
    assert tokens.resolve("g2", t2) == "N"


def test_revoking_a_seat_takes_every_token_that_seat_holds():
    """RT-12a: an unlinked player keeps no working link, however many they had."""
    tokens = InMemorySeatTokens()
    first = tokens.mint("g1", "N")
    second = tokens.mint("g1", "N")
    others = tokens.mint("g1", "E")
    tokens.revoke_seat("g1", "N")
    assert tokens.resolve("g1", first) is None
    assert tokens.resolve("g1", second) is None
    assert tokens.resolve("g1", others) == "E"


def test_revoking_a_seat_of_an_unknown_game_changes_nothing():
    """A console acting on a game this process never had is not an error."""
    tokens = InMemorySeatTokens()
    token = tokens.mint("g1", "N")
    tokens.revoke_seat("gone", "N")
    assert tokens.resolve("g1", token) == "N"
