"""Tests for the battle-event library."""

from simulation.events import immunity, roll, speed_boost, sudden_death
from simulation.physics import Arena, Battle
from simulation.simulate import detect_drops

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)


def test_detect_drops_finds_energy_surges():
    # Sharp low->high energy rises count as drops; sustained sections don't.
    curve = [[0.0, 0.1], [1.0, 0.1], [2.0, 0.1], [3.0, 0.9], [4.0, 0.9],
             [5.0, 0.9], [6.0, 0.2], [7.0, 0.2], [8.0, 0.9], [9.0, 0.9]]
    drops = detect_drops(curve, min_rise=0.4, window_s=1.0, min_gap=3.0)
    assert drops == [3.0, 8.0]


def make_battle(seed: int = 1) -> Battle:
    return Battle(seed=seed, arena=ARENA, ball_radius=38.0, num_balls=5)


def test_sudden_death_schedules_and_emits():
    b = make_battle()
    ev = sudden_death(b, at=50.0)
    assert ev == {"type": "sudden_death", "t": 50.0}
    assert b.sudden_death_at == 50.0
    assert b.events == []                 # scheduled, not yet emitted
    b.time = 50.0
    b._check_events()
    assert b.events == [ev]


def test_sudden_death_immediate_defaults_to_now():
    b = make_battle()
    sudden_death(b)
    assert b.sudden_death_at == 0.0


def test_immunity_gates_elimination():
    b = make_battle()
    b.sudden_death_at = 0.0               # no growth: strings stay at 0
    ev = immunity(b, seconds=20.0)
    assert ev["type"] == "immunity"
    assert b.events == [ev]
    # Zero strings but inside the immunity window: still alive.
    b.balls[0].lifelines = []
    b.step()
    assert b.balls[0].alive
    # Once the window passes, zero strings is fatal again.
    b.immunity_until = 0.0
    b.balls[0].lifelines = []
    b.step()
    assert not b.balls[0].alive


def test_speed_boost_applies_to_field():
    b = make_battle()
    ev = speed_boost(b, seconds=10.0, mult=1.5)
    assert ev["type"] == "speed_boost"
    assert b.speed_boost_mult == 1.5
    assert b.speed_boost_until > b.time
    assert b.events == [ev]


def test_roll_chance_zero_returns_none():
    b = make_battle()
    assert roll(b, b.rng, chance=0.0) is None
    assert b.events == []


def test_roll_chance_one_picks_a_random_event():
    b = make_battle()
    ev = roll(b, b.rng, chance=1.0)
    assert ev is not None
    assert ev["type"] in ("immunity", "speed_boost")
    assert b.events == [ev]
