# pinochle.web.routers.player
from fastapi import APIRouter, Depends, Response

from pinochle.web.card_codec import decode_card, decode_suit
from pinochle.web.container import Container
from pinochle.web.dependencies import get_container, require_seat
from pinochle.web.schemas import (
    AcknowledgeRequest,
    BidRequest,
    ContractRequest,
    DrawRequest,
    PassRequest,
    PlayRequest,
    TrumpRequest,
)

router = APIRouter()

# Every command below requires the seat token of FR-10a and returns 204: the
# resulting game state comes back only on the caller's event stream (§5.1).


@router.post("/api/games/{game_id}/draw", status_code=204)
async def draw(
    game_id: str,
    body: DrawRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Take a card from the face-down dealer-selection spread (FR-11, FR-12)."""
    container.actions.draw_for_deal(game_id, player_id, body.position)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/bid", status_code=204)
async def bid(
    game_id: str,
    body: BidRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Submit a bid or, with ``amount`` omitted, a pass (FR-24–FR-30)."""
    container.actions.place_bid(game_id, player_id, body.amount)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/contract", status_code=204)
async def contract(
    game_id: str,
    body: ContractRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Accept or decline a contract nobody bid against (FR-32)."""
    container.actions.confirm_contract(game_id, player_id, body.accept)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/trump", status_code=204)
async def trump(
    game_id: str,
    body: TrumpRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Declare the trump suit for the round (FR-34)."""
    container.actions.name_trump(game_id, player_id, decode_suit(body.suit))
    return Response(status_code=204)


@router.post("/api/games/{game_id}/pass", status_code=204)
async def pass_cards(
    game_id: str,
    body: PassRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Hand four cards to a partner (FR-37–FR-43)."""
    container.actions.pass_cards(game_id, player_id, [decode_card(c) for c in body.cards])
    return Response(status_code=204)


@router.post("/api/games/{game_id}/begin-play", status_code=204)
async def begin_play(
    game_id: str,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """End the meld display and lead the first trick (FR-50a)."""
    container.actions.begin_play(game_id, player_id)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/toss-in", status_code=204)
async def toss_in(
    game_id: str,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Concede the contract without playing it out (FR-50b)."""
    container.actions.toss_in(game_id, player_id)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/acknowledge", status_code=204)
async def acknowledge(
    game_id: str,
    body: AcknowledgeRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Release the hold the table is stopped on, from any seat (RT-13, UI-19a).

    Returns 204 whether or not the hold was still there to release: a second
    click, or a second player's, is the expected case and not an error.
    """
    container.actions.acknowledge(game_id, player_id, body.hold_id)
    return Response(status_code=204)


@router.post("/api/games/{game_id}/play", status_code=204)
async def play(
    game_id: str,
    body: PlayRequest,
    container: Container = Depends(get_container),
    player_id: str = Depends(require_seat),
) -> Response:
    """Play a card into the current trick (FR-51–FR-53)."""
    container.actions.play_card(game_id, player_id, decode_card(body.card))
    return Response(status_code=204)
