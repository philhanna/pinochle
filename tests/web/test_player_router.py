# tests.web.test_player_router
from pinochle.domain.cards.suit import Suit
from pinochle.services.round import RoundPhase
from pinochle.web.card_codec import encode_card
from tests.web.conftest import seat_players


def seat_headers(token: str) -> dict:
    """The header a player request needs to pass ``require_seat``."""
    return {"X-Seat-Token": token}


def start_and_deal(container, game_id: str) -> None:
    """Seat, start, and deal a round entirely through the service (no HTTP)."""
    for player_id in ("p-north", "p-east", "p-south", "p-west"):
        container.sse.subscribe(game_id, player_id)
    container.admin.start_game(game_id)
    for position, player_id in enumerate(["p-north", "p-east", "p-south", "p-west"]):
        container.actions.draw_for_deal(game_id, player_id, position)
    while container.state.load(game_id).current_round is None:
        taken = container.admin.positions_taken(game_id)
        free = (i for i in range(container.admin.spread_size(game_id)) if i not in taken)
        for player_id in ["p-north", "p-east", "p-south", "p-west"]:
            container.actions.draw_for_deal(game_id, player_id, next(free))


async def test_draw_requires_a_seat_token(container, client):
    """A missing seat token is rejected before any game logic runs."""
    game_id = container.admin.create_game()
    response = await client.post(f"/api/games/{game_id}/draw", json={"position": 0})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_seat"


async def test_a_wrong_game_seat_token_is_rejected(container, client):
    """A token minted for one game must not authorise another (§5.3)."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    other_game_id = container.admin.create_game()
    token = container.tokens.mint(other_game_id, "p-north")

    response = await client.post(
        f"/api/games/{game_id}/draw", json={"position": 0}, headers=seat_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_seat"


async def test_bid_places_a_bid_through_the_wire(container, client):
    """A valid bid should return 204 and be reflected in the round state."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    opener = round_state.current_player
    token = container.tokens.mint(game_id, opener)

    response = await client.post(
        f"/api/games/{game_id}/bid", json={"amount": 250}, headers=seat_headers(token),
    )
    assert response.status_code == 204
    assert round_state.current_high_bid == 250


async def test_a_pass_bid_omits_the_amount(container, client):
    """``{"amount": null}`` is how a pass is spelled on the wire (§5.3)."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    opener = round_state.current_player
    token = container.tokens.mint(game_id, opener)

    response = await client.post(
        f"/api/games/{game_id}/bid", json={"amount": None}, headers=seat_headers(token),
    )
    assert response.status_code == 204
    last_entry = round_state.bid_history[-1]
    assert last_entry.player_id == opener
    assert last_entry.amount is None


async def test_an_illegal_bid_is_rejected_with_409(container, client):
    """A bid below the minimum should surface as illegal_action, not a 500."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    opener = round_state.current_player
    token = container.tokens.mint(game_id, opener)

    response = await client.post(
        f"/api/games/{game_id}/bid", json={"amount": 10}, headers=seat_headers(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "illegal_action"


async def test_an_unparseable_card_code_is_a_422(container, client):
    """design.md §5.5: a malformed card code is a 422, not an unhandled error."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    winner = round_state.current_player
    container.actions.place_bid(game_id, winner, 250)
    for _ in range(3):
        container.actions.place_bid(game_id, round_state.current_player, None)
    container.actions.confirm_contract(game_id, winner, accept=True)
    container.actions.name_trump(game_id, winner, Suit.SPADES)
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        container.actions.pass_cards(game_id, passer, list(round_state.hand(passer))[:4])
    container.actions.begin_play(game_id, winner)
    token = container.tokens.mint(game_id, winner)

    response = await client.post(
        f"/api/games/{game_id}/play", json={"card": "ZZ"}, headers=seat_headers(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_trump_decodes_the_suit_from_the_wire(container, client):
    """The suit name on the wire should reach the round as a domain Suit."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    winner = round_state.current_player
    container.actions.place_bid(game_id, winner, 250)
    for _ in range(3):
        container.actions.place_bid(game_id, round_state.current_player, None)
    container.actions.confirm_contract(game_id, winner, accept=True)
    token = container.tokens.mint(game_id, winner)

    response = await client.post(
        f"/api/games/{game_id}/trump", json={"suit": "HEARTS"}, headers=seat_headers(token),
    )
    assert response.status_code == 204
    assert round_state.trump == Suit.HEARTS


async def test_play_decodes_a_card_from_its_wire_code(container, client):
    """A card code like "TS" should reach the round as the ten of spades."""
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    round_state = container.state.load(game_id).current_round
    winner = round_state.current_player
    container.actions.place_bid(game_id, winner, 250)
    for _ in range(3):
        container.actions.place_bid(game_id, round_state.current_player, None)
    container.actions.confirm_contract(game_id, winner, accept=True)
    container.actions.name_trump(game_id, winner, Suit.SPADES)
    while round_state.phase == RoundPhase.PASSING:
        passer = round_state.current_player
        container.actions.pass_cards(game_id, passer, list(round_state.hand(passer))[:4])
    container.actions.begin_play(game_id, winner)

    legal_card = round_state.legal_plays(winner)[0]
    token = container.tokens.mint(game_id, winner)

    response = await client.post(
        f"/api/games/{game_id}/play",
        json={"card": encode_card(legal_card)},
        headers=seat_headers(token),
    )
    assert response.status_code == 204
    assert legal_card in [play.card for play in round_state.current_trick_plays]


async def test_a_draw_after_the_deal_is_a_409_not_a_500(container, client):
    """NFR-4: a stale tab's draw is refused in words, not with a crash.

    A seat that reconnects mid-round may still be showing the spread it was
    looking at when the deal began. Clicking it must come back as a refusal
    the client can display, like every other out-of-phase action.
    """
    game_id = container.admin.create_game()
    seat_players(container, game_id)
    start_and_deal(container, game_id)
    token = container.tokens.mint(game_id, "p-north")

    response = await client.post(
        f"/api/games/{game_id}/draw", json={"position": 0}, headers=seat_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "wrong_phase"
