"""Tests for the battle-event library."""

from simulation.events import immunity, roll, speed_boost, sudden_death
from simulation.physics import Arena, Battle
from simulation.simulate import _song_energy_level, section_drop_start, simulate

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)


def _plateau_curve(segments):
    """Build a 10 Hz energy curve from (start_s, end_s, value) plateaus."""
    pts = []
    for start, end, val in segments:
        for i in range(int(start * 10), int(end * 10)):
            pts.append([round(i / 10.0, 3), val])
    return pts


def test_song_energy_level_adapts_to_song():
    # A loud song gets a higher pace level than a calm one, but it is a single
    # constant - the battle's base speed scales with the song without pulsing
    # phrase-to-phrase.
    loud = _plateau_curve([(0, 30, 0.8), (30, 60, 0.9)])
    calm = _plateau_curve([(0, 30, 0.2), (30, 60, 0.25)])
    assert _song_energy_level(loud) > _song_energy_level(calm)


def test_section_drop_start_reads_the_analysis():
    # The drop start comes from the timeline's analysed sections - the one
    # source of truth. No sections -> no drop.
    sections = [
        {"label": "intro", "start": 0.0, "end": 15.0},
        {"label": "drop", "start": 46.5, "end": 58.0},
    ]
    assert section_drop_start(sections) == 46.5
    assert section_drop_start([]) is None
    assert section_drop_start(None) is None


def test_simulate_paces_battle_around_the_main_drop():
    # The battle is paced around the analysis's main drop and the drop event
    # fires at that same moment, so the renderer's zoom lands exactly where
    # the field bams back to double speed.
    curve = _plateau_curve([
        (0, 10, 0.2), (10, 40, 0.3), (40, 46, 0.2), (46, 55, 0.8),
        (55, 70, 0.4), (70, 80, 0.5)])
    sections = [{"label": "drop", "start": 46.5, "end": 55.0}]
    events = simulate(seed=6, energy_curve=curve, sections=sections)
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
