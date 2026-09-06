# tests.domain.test_player
import dataclasses

from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID


def test_seats_determine_the_partnership():
    """North and South are partners; East and West are partners."""
    assert Position.NORTH.team_id == NS_TEAM_ID
    assert Position.SOUTH.team_id == NS_TEAM_ID
    assert Position.EAST.team_id == EW_TEAM_ID
    assert Position.WEST.team_id == EW_TEAM_ID


def test_player_team_follows_its_seat():
    """A player's partnership is read from the seat, not supplied separately."""
    player = Player("N", "North", PlayerType.HUMAN, Position.NORTH)
    assert player.team_id == NS_TEAM_ID


def test_partnership_is_not_a_stored_field():
    """There is no team field to set, so an inconsistent pairing cannot exist."""
    fields = {f.name for f in dataclasses.fields(Player)}
    assert "team_id" not in fields
    assert fields == {"id", "name", "type", "position"}
