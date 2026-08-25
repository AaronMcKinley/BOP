#!/usr/bin/env python3
"""mock_stats.py: control the season leaderboard (config/stats.json).

Usage:
  python scripts/mock_stats.py            seed demo standings (tight race)
  python scripts/mock_stats.py --reset    clean zero baseline (fresh season)

The demo standings let you preview the league-table movement animation without
waiting for real battles to accumulate. --reset wipes everything back to zero.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_FILE = ROOT / "config" / "stats.json"

# id, name, points, wins, losses, podiums, kills, eliminations, total_battles
# Points are kept tight so a single battle's +0..+4 reshuffles the standings
# and the table movement animation is easy to see.
MOCK = [
    (1, "blue",   16, 2, 8, 4, 14, 5, 10),
    (0, "red",    15, 2, 8, 4, 13, 4, 10),
    (4, "purple", 14, 1, 9, 3, 12, 4, 10),
    (2, "green",  13, 1, 9, 3, 11, 3, 10),
    (3, "yellow", 12, 1, 9, 2, 10, 3, 10),
    (5, "orange", 11, 0, 9, 1,  9, 2, 10),
]


def zero_stats() -> dict:
    """A clean baseline: every ball with zero season history."""
    balls = []
    for bid, name in [(0, "red"), (1, "blue"), (2, "green"), (3, "yellow"),
                      (4, "purple"), (5, "orange")]:
        balls.append({
            "id": bid,
            "name": name,
            "points": 0,
            "wins": 0,
            "losses": 0,
            "podiums": 0,
            "kills": 0,
            "eliminations": 0,
            "lifeline_cuts": 0,
            "collisions": 0,
            "total_battles": 0,
        })
    return {"battle_count": 0, "season": 1, "balls": balls}


def main():
    if "--reset" in sys.argv[1:]:
        STATS_FILE.write_text(json.dumps(zero_stats(), indent=2), encoding="utf-8")
        print(f"reset {STATS_FILE} to a clean zero baseline")
        print("run without --reset to seed the demo standings instead")
        return

    balls = []
    for bid, name, points, wins, losses, podiums, kills, eliminations, total in MOCK:
        balls.append({
            "id": bid,
            "name": name,
            "points": points,
            "wins": wins,
            "losses": losses,
            "podiums": podiums,
            "kills": kills,
            "eliminations": eliminations,
            "lifeline_cuts": 0,
            "collisions": 0,
            "total_battles": total,
        })
    data = {"battle_count": 0, "season": 1, "balls": balls}
    STATS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"wrote mock standings to {STATS_FILE}")
    print("\nrank  name     pts   W  podiums  kills")
    for ball in sorted(balls, key=lambda b: (-b["points"], -b["wins"], b["id"])):
        print(f"  {ball['name']:8s} {ball['points']:3d}  {ball['wins']}  "
              f"{ball['podiums']:2d}      {ball['kills']:3d}")


if __name__ == "__main__":
    main()
