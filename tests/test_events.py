"""Tests for the battle-event library."""

from simulation.events import immunity, roll, speed_boost, sudden_death
from simulation.physics import Arena, Battle
from simulation.simulate import _song_energy_level, detect_drops, main_drop, simulate

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)


def test_detect_drops_finds_energy_surges():
    # Sharp low->high energy rises count as drops; sustained sections don't.
    # (Explicit thresholds here - the defaults are song-relative.)
    curve = [[0.0, 0.1], [1.0, 0.1], [2.0, 0.1], [3.0, 0.9], [4.0, 0.9],
             [5.0, 0.9], [6.0, 0.2], [7.0, 0.2], [8.0, 0.9], [9.0, 0.9]]
    drops = detect_drops(curve, min_rise=0.4, window_s=1.0, min_gap=3.0,
                         min_land=0.45)
    assert drops == [3.0, 8.0]


def _plateau_curve(segments):
    """Build a 10 Hz energy curve from (start_s, end_s, value) plateaus."""
    pts = []
    for start, end, val in segments:
        for i in range(int(start * 10), int(end * 10)):
            pts.append([round(i / 10.0, 3), val])
    return pts


def _pulse_train():
    # A low-contrast song: it pulses 0.2 -> 0.6 every ~9s all the way through,
    # with one surge that stands out (0.2 -> 0.8 at 30-36s).
    return _plateau_curve([
        (0, 3, 0.2), (3, 9, 0.6), (9, 12, 0.2), (12, 18, 0.6), (18, 21, 0.2),
        (21, 27, 0.6), (27, 30, 0.2), (30, 36, 0.8), (36, 39, 0.2),
        (39, 45, 0.6), (45, 48, 0.2), (48, 54, 0.6)])


def test_detect_drops_are_song_relative():
    # Every pulse in the train is a genuine energy rise that an absolute
    # threshold would call a drop. The song-relative default only keeps the
    # one surge that stands out (to 0.8), like Cradles' repeated phrase pulses
    # collapsing to a handful of real moments.
    assert detect_drops(_pulse_train()) == [33.3]


def test_detect_drops_finds_sustained_surge():
    # The big sustained surge (0.8 from 30s) is the song's drop; the quiet
    # build-up to 0.45 before it is not.
    curve = _plateau_curve([(0, 15, 0.15), (15, 30, 0.45), (30, 45, 0.8),
                            (45, 60, 0.3)])
    assert detect_drops(curve) == [30.5]


def test_main_drop_picks_latest_surge():
    # Drops at 3.0 and 7.0 - the latest one (7.0) is the finale trigger.
    curve = [[0.0, 0.1], [1.0, 0.1], [2.0, 0.1], [3.0, 0.7], [4.0, 0.7],
             [5.0, 0.2], [6.0, 0.2], [7.0, 0.95], [8.0, 0.95], [9.0, 0.95]]
    assert main_drop(curve, min_rise=0.4, window_s=1.0, min_gap=3.0,
                     min_land=0.45) == 7.0


def test_main_drop_honours_limit():
    # The strongest surge is at 7.0, but a battle that ends at 5.0 must use the
    # strongest surge *inside* the battle (3.0), not one that never happens.
    curve = [[0.0, 0.1], [1.0, 0.1], [2.0, 0.1], [3.0, 0.7], [4.0, 0.7],
             [5.0, 0.2], [6.0, 0.2], [7.0, 0.95], [8.0, 0.95], [9.0, 0.95]]
    assert main_drop(curve, min_rise=0.4, window_s=1.0, min_gap=3.0,
                     min_land=0.45, limit=5.0) == 3.0


def test_main_drop_none_when_battle_ends_before_drop():
    # The song's only surge lands at 33.3s - a battle that ends before it has
    # no drop to punctuate the finale with.
    assert main_drop(_pulse_train(), limit=29.0) is None
    assert main_drop(_pulse_train(), limit=40.0) == 33.3


def test_song_energy_level_adapts_to_song():
    # A loud song gets a higher pace level than a calm one, but it is a single
    # constant - the battle's base speed scales with the song without pulsing
    # phrase-to-phrase.
    loud = _plateau_curve([(0, 30, 0.8), (30, 60, 0.9)])
    calm = _plateau_curve([(0, 30, 0.2), (30, 60, 0.25)])
    assert _song_energy_level(loud) > _song_energy_level(calm)


def test_simulate_paces_battle_around_the_main_drop():
    # The battle is paced around the one main drop (the 40-70s range) and the
    # drop event fires at that same moment, so the renderer's zoom lands
    # exactly where the field bams back to full speed.
    curve = _plateau_curve([
        (0, 10, 0.2), (10, 40, 0.3), (40, 46, 0.2), (46, 55, 0.8),
        (55, 70, 0.4), (70, 80, 0.5)])
    events = simulate(seed=6, energy_curve=curve)
    drops = [e for e in events["events"] if e["type"] == "drop"]
    assert drops == [{"type": "drop", "t": 46.5}]


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
