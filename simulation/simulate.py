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


def detect_drops(energy_curve: list, min_rise: float = 0.3, min_gap: float = 6.0,
                 window_s: float = 1.5) -> list:
    """Musical drops: sharp low->high energy surges in the song.

    A drop is an energy rise of at least `min_rise` over a ~`window_s` window
    that lands at high energy. Returns the times (song seconds) of the surges,
    at least `min_gap` seconds apart.
    """
    drops = []
    if len(energy_curve) < 2:
        return drops
    dt = max(energy_curve[1][0] - energy_curve[0][0], 0.001)
    n = max(1, int(round(window_s / dt)))
    last_t = -min_gap
    for i in range(n, len(energy_curve)):
        t, e = energy_curve[i]
        t0, e0 = energy_curve[i - n]
        if t - last_t >= min_gap and e - e0 >= min_rise and e >= 0.45:
            drops.append(round(t, 2))
            last_t = t
    return drops


def simulate(seed: int, num_balls: int = 5, ball_radius: float = 38.0,
             event_chance: float = 0.0, energy_curve: Optional[list] = None) -> dict:
    """Run a battle to its end and return the events.json dict.

    event_chance is the probability a random battle event fires (immunity /
    speed boost); 0 (default) disables random events entirely. Sudden death
    stays as the scheduled 90 s backstop either way.

    energy_curve (from the song's timeline) drives the field speed: the battle
    drifts in the intro, slams at the drop, eases in the breakdown. Without it
    the speed follows the plain time-based ramp.
    """
    battle = Battle(seed=seed, arena=ARENA, ball_radius=ball_radius, num_balls=num_balls)
    if energy_curve:
        battle.energy_curve = energy_curve
    battle_events.roll(battle, battle.rng, chance=event_chance)
    frames = []
    while not battle.is_over():
        frames.append({"t": round(battle.time, 6), "balls": battle.frame_state()})
        battle.step()

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
    # Musical drops: sharp low->high energy surges in the song. The renderer
    # reacts to each with a camera jump + zoom, so the drop feels part of the
    # action. Only drops that land before the battle ends matter.
    if energy_curve:
        drops = [{"type": "drop", "t": t} for t in detect_drops(energy_curve)
                 if t <= battle.time]
        if drops:
            events["events"] = sorted(battle.events + drops, key=lambda e: e["t"])
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
