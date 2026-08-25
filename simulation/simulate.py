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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def simulate(seed: int, num_balls: int = 5, ball_radius: float = 38.0) -> dict:
    """Run a battle to its end and return the events.json dict."""
    battle = Battle(seed=seed, arena=ARENA, ball_radius=ball_radius, num_balls=num_balls)
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
    }
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
    args = parser.parse_args()

    used_seeds = set(load_used_seeds(args.used_seeds))

    if args.seed is not None:
        # An explicit seed is always respected, but warn if it was already used.
        if args.seed in used_seeds:
            print(f"WARNING: seed {args.seed} was already used (see {args.used_seeds})")
        events = simulate(args.seed, args.balls)
    else:
        # Fresh random seed each attempt; skip seeds already used in published
        # battles, and re-roll until the battle is long enough (the battle length
        # varies wildly per seed, so this guarantees a usable one).
        for _ in range(50):
            seed = random.SystemRandom().randint(0, 2 ** 31)
            if seed in used_seeds:
                continue
            events = simulate(seed, args.balls)
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
    print(f"wrote {out}")
