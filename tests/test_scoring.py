"""Tests for the shared scoring module (positions, points, leaderboard)."""

from simulation.scoring import (
    battle_points,
    finishing_positions,
    leaderboard_after,
    leaderboard_current,
)


def _events(winner=2, eliminations=None):
    return {
        "winner": {"ball_id": winner, "t": 10.0},
        "eliminations": eliminations or [],
    }


def test_finishing_positions_winner_first():
    events = _events(winner=1, eliminations=[
        {"t": 5.0, "ball_id": 4},
        {"t": 6.0, "ball_id": 2},
        {"t": 7.0, "ball_id": 0},
        {"t": 8.0, "ball_id": 3},
    ])
    positions = finishing_positions(events)
    assert positions[1] == 1          # winner
    assert positions[3] == 2          # last eliminated
    assert positions[0] == 3
    assert positions[2] == 4
    assert positions[4] == 5          # first eliminated


def test_finishing_positions_no_eliminations():
    # Winner is always 1st even with an empty elimination log.
    assert finishing_positions(_events(winner=0)) == {0: 1}


def test_battle_points_mapping():
    positions = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
    assert battle_points(positions) == {0: 4, 1: 3, 2: 2, 3: 1, 4: 0}


def test_leaderboard_current_sorted():
    stats = {"balls": [
        {"id": 0, "name": "red", "points": 2, "wins": 1, "kills": 5},
        {"id": 1, "name": "blue", "points": 6, "wins": 2, "kills": 9},
        {"id": 2, "name": "green", "points": 0, "wins": 0, "kills": 0},
    ]}
    rows = leaderboard_current(stats)
    assert [r["id"] for r in rows] == [1, 0, 2]
    assert rows[0]["position"] == 1


def test_leaderboard_kills_tiebreak_equal_points():
    # Equal points are ordered by kills - the table moves on kills, not just id.
    stats = {"balls": [
        {"id": 0, "name": "red", "points": 4, "wins": 1, "kills": 2},
        {"id": 1, "name": "blue", "points": 4, "wins": 2, "kills": 7},
        {"id": 2, "name": "green", "points": 4, "wins": 2, "kills": 7},
    ]}
    rows = leaderboard_current(stats)
    # blue (7 kills) ahead of red (2 kills); wins then id breaks the blue/green tie.
    assert [r["id"] for r in rows] == [1, 2, 0]


def test_leaderboard_after_kills_tiebreak():
    # Two balls end on the same points; the one with more kills ranks higher.
    stats = {"balls": [
        {"id": 0, "name": "red", "points": 1, "wins": 0, "kills": 1},
        {"id": 1, "name": "blue", "points": 2, "wins": 0, "kills": 1},
    ]}
    positions = {0: 2, 1: 3}                    # 3 and 2 points this battle
    points = battle_points(positions)            # {0: 3, 1: 2}
    battle_stats = {0: {"kills": 5}, 1: {"kills": 0}}
    rows = leaderboard_after(stats, positions, points, battle_stats)
    # Both end on 4 points; red (6 kills) beats blue (1 kill).
    assert [r["id"] for r in rows] == [0, 1]


def test_leaderboard_after_accumulates():
    stats = {"balls": [
        {"id": 0, "name": "red", "points": 2, "wins": 0, "kills": 1},
        {"id": 1, "name": "blue", "points": 3, "wins": 0, "kills": 1},
        {"id": 2, "name": "green", "points": 0, "wins": 0, "kills": 0},
    ]}
    positions = {0: 2, 1: 1, 2: 3}
    points = battle_points(positions)   # {0: 3, 1: 4, 2: 2}
    battle_stats = {0: {"kills": 2}, 1: {"kills": 3}, 2: {"kills": 0}}

    rows = leaderboard_after(stats, positions, points, battle_stats)
    by_id = {r["id"]: r for r in rows}

    assert by_id[1]["points"] == 7     # 3 + 4
    assert by_id[1]["wins"] == 1
    assert by_id[1]["podiums"] == 1
    assert by_id[1]["delta"] == 4
    assert by_id[1]["kills"] == 4      # 1 lifetime + 3 this battle
    assert by_id[1]["position"] == 1

    assert by_id[0]["points"] == 5     # 2 + 3
    assert by_id[0]["position"] == 2
    assert by_id[2]["points"] == 2
    assert by_id[2]["position"] == 3

    # Sorted by points descending.
    assert [r["id"] for r in rows] == [1, 0, 2]


def test_leaderboard_after_handles_int_or_str_stats_keys():
    # battle stats keys are ints in memory but strings after JSON round-trip.
    stats = {"balls": [{"id": 0, "name": "red", "points": 0, "wins": 0, "kills": 0}]}
    positions = {0: 1}
    points = battle_points(positions)
    a = leaderboard_after(stats, positions, points, {0: {"kills": 2}})
    b = leaderboard_after(stats, positions, points, {"0": {"kills": 2}})
    assert a[0]["kills"] == 2
    assert b[0]["kills"] == 2


def test_leaderboard_after_skips_non_participants():
    stats = {"balls": [
        {"id": 0, "name": "red", "points": 0, "wins": 0, "kills": 0},
        {"id": 1, "name": "blue", "points": 5, "wins": 0, "kills": 0},   # not in this battle
    ]}
    positions = {0: 1}
    rows = leaderboard_after(stats, positions, battle_points(positions))
    assert len(rows) == 1
    assert rows[0]["id"] == 0


def test_simulate_embeds_scoring_data():
    from simulation.simulate import simulate

    events = simulate(seed=99, num_balls=5)
    wid = events["winner"]["ball_id"]
    assert events["positions"][wid] == 1
    assert events["points"][wid] == 4
    assert isinstance(events["leaderboard"], list)
    assert events["leaderboard"][0]["position"] == 1
    assert events["leaderboard_before"] != {}
