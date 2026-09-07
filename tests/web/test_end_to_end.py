# tests.web.test_end_to_end
from pinochle.adapters.fake_scheduler import FakeScheduler
from pinochle.domain.game import GamePhase
from pinochle.domain.player import Player, PlayerType, Position
from pinochle.domain.team import EW_TEAM_ID, NS_TEAM_ID, Team
from pinochle.web.container import Settings, build_container


def test_an_all_computer_game_completes_through_the_full_container():
    """design.md §13 step 7's milestone: a complete, exercisable server.

    Exercises the same wiring production uses (SseNotification,
    LoggingNotification, seat tokens, the computer driver) rather than a
    bespoke minimal service, with only the scheduler and the shuffle seed
    swapped for deterministic, real-time-free ones.
    """
    settings = Settings(
        admin_token="tok", computer_delay_seconds=0, trick_clear_seconds=0, shuffle_seed=7,
    )
    scheduler = FakeScheduler()
    container = build_container(settings, scheduler=scheduler)

    game_id = container.admin.create_game()
    container.admin.assign_teams(game_id, Team(NS_TEAM_ID, "Us"), Team(EW_TEAM_ID, "Them"))
    for player_id, name, position in [
        ("p-north", "North", Position.NORTH),
        ("p-east", "East", Position.EAST),
        ("p-south", "South", Position.SOUTH),
        ("p-west", "West", Position.WEST),
    ]:
        container.admin.add_player(
            game_id, Player(player_id, name, PlayerType.COMPUTER, position),
        )
    container.admin.start_game(game_id)

    for _ in range(20000):
        if container.state.load(game_id).phase == GamePhase.FINISHED:
            break
        scheduler.advance(0)
    else:
        raise AssertionError("game never reached FINISHED")

    game = container.state.load(game_id)
    scores = {team_id: team.cumulative_score for team_id, team in game.teams.items()}
    assert max(scores.values()) >= 2000
