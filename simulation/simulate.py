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

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)


def simulate(seed: int, num_balls: int = 5, ball_radius: float = 38.0) -> dict:
    """Run a battle to its end and return the events.json dict."""
    battle = Battle(seed=seed, arena=ARENA, ball_radius=ball_radius, num_balls=num_balls)
    frames = []
    while not battle.is_over():
        frames.append({"t": round(battle.time, 6), "balls": battle.frame_state()})
        battle.step()

    return {
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an arena battle and write events.json.")
    parser.add_argument("--seed", type=int, default=None,
                        help="battle seed (default: fresh random seed)")
    parser.add_argument("--balls", type=int, default=5, help="number of balls (default 5)")
    parser.add_argument("--out", type=str, required=True, help="output events.json path")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.SystemRandom().randint(0, 2 ** 31)
    events = simulate(seed, args.balls)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=1), encoding="utf-8")

    print(f"seed={seed}  winner={events['winner']['ball_id']}  "
          f"duration={events['duration_s']}s  frames={len(events['frames'])}")
    print(f"eliminations={len(events['eliminations'])}  collisions={len(events['collisions'])}")
    print(f"wrote {out}")
