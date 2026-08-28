"""simulate.py: run an arena battle and write events.json.

The video length is the battle length - it runs until one ball remains
(or the physics safety cap), not a fixed duration.

Usage:
  python simulation/simulate.py --seed 4821 --balls 5 --out output/events/track.json
  (omit --seed for a fresh random battle every run)
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation import events as battle_events
from simulation.physics import Arena, Battle
from simulation.scoring import (
    battle_points,
    finishing_positions,
    leaderboard_after,
    leaderboard_current,
)
from simulation.seed_registry import DEFAULT_PATH as USED_SEEDS_FILE, load_used_seeds

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)
STATS_FILE = Path(__file__).resolve().parent.parent / "config" / "stats.json"

# Drop detection is song-relative: the same absolute rise can be a huge moment
# for a calm track and a non-event for a wall of sound, so the thresholds come
# from the song's own energy distribution instead of fixed numbers.
DROP_WINDOW_S = 6.0     # phrase-scale window: a drop is a whole-phrase surge
DROP_MIN_GAP_S = 10.0   # keep qualifying drops apart (one per phrase-ish)
DROP_RISE_PCT = 90.0    # a drop's rise must beat 90% of this song's rises
DROP_LAND_PCT = 80.0    # ... and land in the top 20% of this song's energy
DROP_SMOOTH_S = 1.0     # smooth the curve first so single kick-spikes don't count
DROP_SELECT_LIMIT_S = 70.0  # THE main drop is picked in the song's usual drop
                            # range (40s-1:10), not wherever the battle ends
SONG_LEVEL_SMOOTH_S = 3.5   # smoothing used to estimate the song's overall level
SONG_LEVEL_FLOOR = 0.3      # ... clamped so a very quiet song still fights


def _song_energy_level(energy_curve: list) -> float:
    """A single "how intense is this song" number - the median of its smoothed
    energy. It scales the battle's base pace (loud songs race, calm ones
    cruise) as a constant, so the field never pulses phrase-to-phrase. The
    smoothing here only stabilises the median estimate; it is not a drive curve.
    """
    if len(energy_curve) < 2:
        return 1.0
    dt = max(energy_curve[1][0] - energy_curve[0][0], 0.001)
    win = max(1, int(round(SONG_LEVEL_SMOOTH_S / dt)))
    energies = np.convolve(
        [e for _, e in energy_curve], np.ones(win) / win, mode="same")
    return max(SONG_LEVEL_FLOOR, min(1.0, float(np.median(energies))))


def _drop_candidates(energy_curve: list, min_rise: Optional[float],
                     min_gap: float, window_s: float,
                     min_land: Optional[float]) -> list:
    """Qualifying drop times for a song's energy curve.

    A drop is a phrase-scale energy surge that stands out *for this song*:
    its rise over `window_s` must beat DROP_RISE_PCT of the song's own phrase
    rises, and its landing must sit above DROP_LAND_PCT of the song's energy.
    Explicit min_rise / min_land override the song-relative values (for
    tuning / tests).
    """
    if len(energy_curve) < 2:
        return []
    dt = max(energy_curve[1][0] - energy_curve[0][0], 0.001)
    win = max(1, int(round(DROP_SMOOTH_S / dt)))
    energies = np.convolve(
        [e for _, e in energy_curve], np.ones(win) / win, mode="same")
    n = max(1, int(round(window_s / dt)))
    rises = energies[n:] - energies[:-n]
    lands = energies[n:]

    pos = rises[rises > 0]
    rise_thresh = float(np.percentile(pos, DROP_RISE_PCT)) if pos.size else 0.0
    land_thresh = float(np.percentile(lands, DROP_LAND_PCT))
    if min_rise is not None:
        rise_thresh = min_rise
    if min_land is not None:
        land_thresh = min_land

    drops = []
    last_t = -min_gap
    for i in range(n, len(energy_curve)):
        t = energy_curve[i][0]
        if t - last_t >= min_gap and rises[i - n] >= rise_thresh \
                and lands[i - n] >= land_thresh:
            drops.append(round(t, 2))
            last_t = t
    return drops


def detect_drops(energy_curve: list, min_rise: Optional[float] = None,
                 min_gap: float = DROP_MIN_GAP_S, window_s: float = DROP_WINDOW_S,
                 min_land: Optional[float] = None) -> list:
    """Musical drops: phrase-scale energy surges that stand out for THIS song.

    Returns the times (song seconds) of the qualifying surges, at least
    `min_gap` apart. The thresholds are derived from the song's own energy
    distribution (see _drop_candidates) rather than fixed absolute numbers.
    """
    return _drop_candidates(energy_curve, min_rise, min_gap, window_s, min_land)


def main_drop(energy_curve: list, min_rise: Optional[float] = None,
              min_gap: float = DROP_MIN_GAP_S, window_s: float = DROP_WINDOW_S,
              min_land: Optional[float] = None, limit: float = None):
    """The drop that lands closest to the battle's end, or None if none qualify.

    Every qualifying surge triggers the same camera slam, so the LATEST one is
    chosen - it lands right before the finale push-in, which is the moment the
    drop is meant to punctuate.

    `limit` (optional) caps the search at that song time (e.g. the battle
    length), so a song whose real drop is past the battle still gets its last
    surge *inside* the fight.
    """
    within = [t for t in _drop_candidates(energy_curve, min_rise, min_gap,
                                          window_s, min_land)
              if limit is None or t <= limit]
    return within[-1] if within else None


def simulate(seed: int, num_balls: int = 5, ball_radius: float = 38.0,
             event_chance: float = 0.0, energy_curve: Optional[list] = None) -> dict:
    """Run a battle to its end and return the events.json dict.

    event_chance is the probability a random battle event fires (immunity /
    speed boost); 0 (default) disables random events entirely. Sudden death
    stays as the scheduled 90 s backstop either way.

    energy_curve (from the song's timeline) is used to find THE main drop,
    which drives the battle's pacing: the field eases down just before it and
    snaps back to full speed AT it (see drop_speed_multiplier). Without a
    timeline the speed follows the plain time-based ramp.
    """
    battle = Battle(seed=seed, arena=ARENA, ball_radius=ball_radius, num_balls=num_balls)
    # THE one main drop, picked before the battle so the pacing can lead up to
    # it. Chosen in the song's usual drop range (40s-1:10) rather than
    # whichever surge happens to be nearest the battle's end.
    main_drop_at = None
    if energy_curve:
        main_drop_at = main_drop(energy_curve, limit=DROP_SELECT_LIMIT_S)
        if main_drop_at is not None:
            battle.main_drop_at = main_drop_at
            battle.speed_level = _song_energy_level(energy_curve)
    battle_events.roll(battle, battle.rng, chance=event_chance)
    frames = []
    while not battle.is_over():
        frames.append({"t": round(battle.time, 6), "balls": battle.frame_state()})
        battle.step()
    # The resolved end state: the last step eliminated the runner-up, so the
    # final frame must capture the winner alone (the renderer freezes on this
    # frame for the winner hold). 10ms past the last event so the final kill
    # burst renders too.
    frames.append({"t": round(battle.time + 0.01, 6), "balls": battle.frame_state()})

    events = {
        "seed": seed,
        "fps": 60,
        "duration_s": round(battle.time, 3),
        "frames": frames,
        "collisions": battle.collisions,
        "wall_bounces": battle.wall_bounces,
        "eliminations": battle.eliminations,
        # Flat for now; the director fills these with music-driven curves later.
        "pulse_curve": [[0.0, 1.0], [round(battle.time, 3), 1.0]],
        "speed_curve": [[0.0, 1.0], [round(battle.time, 3), 1.0]],
        "winner": {"ball_id": battle.winner, "t": round(battle.time, 3)},
        "stats": battle.stats(),
        # One-per-battle event log: sudden death (90 s, stops lifeline growth)
        # and musical drops (the renderer punches the camera on each) slot into
        # the same channel as immunity / walls / speed boosts.
        "events": battle.events,
    }
    # The drop event fires at the same time the battle's speed bams, so the
    # renderer's camera zoom lands exactly on the action. Only if the battle
    # lasted long enough to reach the drop.
    if main_drop_at is not None and main_drop_at <= battle.time:
        events["events"] = sorted(
            battle.events + [{"type": "drop", "t": main_drop_at}], key=lambda e: e["t"])
    # Scoring: finishing positions, points, and the standings before/after this
    # battle (the end-of-video winner/table sequence reads these, and the table
    # needs "before" to show who moved).
    positions = finishing_positions(events)
    points = battle_points(positions)
    events["positions"] = positions
    events["points"] = points
    try:
        with open(STATS_FILE, encoding="utf-8") as f:
            stats = json.load(f)
        events["leaderboard_before"] = {
            r["id"]: r["position"] for r in leaderboard_current(stats)
        }
        events["leaderboard"] = leaderboard_after(stats, positions, points, events["stats"])
    except (OSError, json.JSONDecodeError):
        # Missing/broken stats file - the table just renders empty.
        events["leaderboard_before"] = {}
        events["leaderboard"] = []
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an arena battle and write events.json.")
    parser.add_argument("--seed", type=int, default=None,
                        help="battle seed (default: fresh random seed)")
    parser.add_argument("--balls", type=int, default=5, help="number of balls (default 5)")
    parser.add_argument("--out", type=str, required=True, help="output events.json path")
    parser.add_argument("--min-duration", type=float, default=0.0,
                        help="when no --seed is given, re-roll seeds until the battle "
                             "is at least this long (seconds)")
    parser.add_argument("--used-seeds", type=str, default=str(USED_SEEDS_FILE),
                        help="json list of seeds already used; fresh rolls skip them "
                             "(default config/used_seeds.json)")
    parser.add_argument("--event-chance", type=float, default=0.0,
                        help="probability a random battle event fires (0 = none, "
                             "default 0)")
    parser.add_argument("--timeline", type=str, default="",
                        help="song timeline.json; its energy curve drives the field "
                             "speed (default: time-based ramp)")
    args = parser.parse_args()

    used_seeds = set(load_used_seeds(args.used_seeds))

    energy_curve = None
    if args.timeline:
        with open(args.timeline, encoding="utf-8") as f:
            energy_curve = json.load(f).get("energy_curve", [])

    if args.seed is not None:
        # An explicit seed is always respected, but warn if it was already used.
        if args.seed in used_seeds:
            print(f"WARNING: seed {args.seed} was already used (see {args.used_seeds})")
        events = simulate(args.seed, args.balls, event_chance=args.event_chance,
                          energy_curve=energy_curve)
    else:
        # Fresh random seed each attempt; skip seeds already used in published
        # battles, and re-roll until the battle is long enough (the battle length
        # varies wildly per seed, so this guarantees a usable one).
        for _ in range(50):
            seed = random.SystemRandom().randint(0, 2 ** 31)
            if seed in used_seeds:
                continue
            events = simulate(seed, args.balls, event_chance=args.event_chance,
                              energy_curve=energy_curve)
            if events["duration_s"] >= args.min_duration:
                break
            print(f"battle too short ({events['duration_s']:.0f}s < {args.min_duration:.0f}s), re-rolling...")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Compact JSON: with dense string webs these files can get large, and the
    # indentation whitespace is pure overhead for the Godot parser.
    out.write_text(json.dumps(events, separators=(",", ":")), encoding="utf-8")

    print(f"seed={events['seed']}  winner={events['winner']['ball_id']}  "
          f"duration={events['duration_s']}s  frames={len(events['frames'])}")
    print(f"eliminations={len(events['eliminations'])}  collisions={len(events['collisions'])}")
    if events["events"]:
        print("events: " + ", ".join(f"{e['type']}@{e['t']}s" for e in events["events"]))
    print(f"wrote {out}")
