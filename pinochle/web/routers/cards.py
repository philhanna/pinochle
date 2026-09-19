# pinochle.web.routers.cards
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from pinochle.web.card_codec import decode_card
from pinochle.web.container import Container
from pinochle.web.dependencies import get_container

router = APIRouter()

# Card artwork never changes for a given URL, so the browser may keep it for
# as long as it likes.  This matters more than it looks: a fanned hand plus
# three fans of backs is ~50 image requests per render (UI-4, UI-5).
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}

_FORMATS = {"svg": "image/svg+xml", "png": "image/png"}

# A card back is named by the client, so it is the one part of these paths
# that could otherwise reach outside the asset directory.  Anything but a
# plain lowercase asset name is refused before it reaches the adapter.
_BACK_NAME = re.compile(r"^[a-z0-9_]{1,40}$")


@router.get("/cards/faces/{code}")
async def card_face(code: str, fmt: str = "svg", container: Container = Depends(get_container)):
    """Serve the face image for a card, named by its wire code (UI-16).

    ``code`` is the same two-character form the event stream uses — ``TS``
    is the ten of spades — so a client renders straight from the codes it
    was sent, with no second naming scheme to keep in step.  An unparseable
    code is a 422 (``decode_card`` raises ``ValueError``); a well-formed
    code with no artwork on disk is a 404.
    """
    media_type = _media_type(fmt)
    path = container.cards.get_image_path(decode_card(code.upper()), fmt=fmt)
    return FileResponse(path, media_type=media_type, headers=_IMMUTABLE)


@router.get("/cards/backs/{name}")
async def card_back(name: str, fmt: str = "svg", container: Container = Depends(get_container)):
    """Serve a named card back image (UI-5, UI-16)."""
    media_type = _media_type(fmt)
    if not _BACK_NAME.match(name):
        raise ValueError(f"{name!r} is not a valid card back name.")
    path = container.cards.get_back_path(fmt=fmt, name=name)
    return FileResponse(path, media_type=media_type, headers=_IMMUTABLE)


def _media_type(fmt: str) -> str:
    """Return the content type for ``fmt``, rejecting anything else.

    Raising ``ValueError`` rather than checking membership inline keeps the
    unknown-format case on the same 422 path as an unparseable card code.
    """
    try:
        return _FORMATS[fmt]
    except KeyError:
        raise ValueError(f"{fmt!r} is not a supported image format.") from None
