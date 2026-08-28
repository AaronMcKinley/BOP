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

# Drop detection lives in analysis/analyze.py - the timeline's sections are the
# ONE source of truth for where the drop starts; simulate.py just reads it.
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


def section_drop_start(sections: Optional[list] = None) -> Optional[float]:
    """The drop start from the song's analysis - the one source of truth.

    analysis/analyze.py detects the drop section for every song; this is the
    moment the choreography leads up to (slow-mo before it, zoom + double speed
    AT it). None when the analysis found no drop.
    """
    for s in sections or []:
        if s.get("label") == "drop":
            return float(s["start"])
    return None


def simulate(seed: int, num_balls: int = 5, ball_radius: float = 38.0,
             event_chance: float = 0.0, energy_curve: Optional[list] = None,
             sections: Optional[list] = None) -> dict:
    """Run a battle to its end and return the events.json dict.

    event_chance is the probability a random battle event fires (immunity /
    speed boost); 0 (default) disables random events entirely. Sudden death
    stays as the scheduled 90 s backstop either way.

    sections (the song's analysed timeline sections) carry THE main drop start;
    it drives the battle's pacing - the field eases down just before it and
    snaps back to double speed AT it (see drop_speed_multiplier). energy_curve
    scales the overall pace to the song.
    """
    battle = Battle(seed=seed, arena=ARENA, ball_radius=ball_radius, num_balls=num_balls)
    # THE one main drop, from the analysis (one source of truth). Picked before
    # the battle so the pacing can lead up to it.
    main_drop_at = None
    if energy_curve:
        battle.speed_level = _song_energy_level(energy_curve)
        main_drop_at = section_drop_start(sections)
        if main_drop_at is not None:
            battle.main_drop_at = main_drop_at
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
    sections = None
    if args.timeline:
        with open(args.timeline, encoding="utf-8") as f:
            timeline = json.load(f)
        energy_curve = timeline.get("energy_curve", [])
        sections = timeline.get("sections", [])

    if args.seed is not None:
        # An explicit seed is always respected, but warn if it was already used.
        if args.seed in used_seeds:
            print(f"WARNING: seed {args.seed} was already used (see {args.used_seeds})")
        events = simulate(args.seed, args.balls, event_chance=args.event_chance,
                          energy_curve=energy_curve, sections=sections)
    else:
        # Fresh random seed each attempt; skip seeds already used in published
        # battles, and re-roll until the battle is long enough (the battle length
        # varies wildly per seed, so this guarantees a usable one).
        for _ in range(50):
            seed = random.SystemRandom().randint(0, 2 ** 31)
            if seed in used_seeds:
                continue
            events = simulate(seed, args.balls, event_chance=args.event_chance,
                              energy_curve=energy_curve, sections=sections)
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
