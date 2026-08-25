#!/usr/bin/env python3
"""publish_battle.py: promote a rendered battle to the publish folder + update stats.

Run scripts/dev_render.sh first and watch the result. If the battle is a
keeper, run this second script: it MOVES the video into
output/publish/<song-name>/ (battle number auto-increments, never overwrites),
writes its metadata, updates the season leaderboard (config/stats.json), and
records the battle's seed in config/used_seeds.json so the same battle is
never simulated again. Only the newest --max videos per song are kept.

The publish folder is the staging area for the later "save as draft" step on
social channels.

Usage:
  python scripts/publish_battle.py --video output/renders/current.mp4 \
      --events output/events/current.json --song MONODY-BIMONTE-REMIX
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.scoring import battle_points, finishing_positions
from simulation.seed_registry import DEFAULT_PATH as USED_SEEDS_FILE, record_seed

STATS_FILE = ROOT / "config" / "stats.json"
PUBLISH_ROOT = ROOT / "output" / "publish"
DEFAULT_MAX_PER_SONG = 10
SEASON = 1


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Promote a battle to publish + update stats.")
    parser.add_argument("--video", required=True, help="the mp4 you just rendered and liked")
    parser.add_argument("--events", required=True, help="events.json for this battle")
    parser.add_argument("--song", required=True, help="song name (used for the publish folder)")
    parser.add_argument("--stats", default=str(STATS_FILE),
                        help="leaderboard json path (default config/stats.json)")
    parser.add_argument("--publish", default=str(PUBLISH_ROOT),
                        help="publish root folder (default output/publish)")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_PER_SONG,
                        help="keep only this many newest videos per song (default 10)")
    parser.add_argument("--used-seeds", type=str, default=str(USED_SEEDS_FILE),
                        help="json list of seeds already used; the battle's seed is "
                             "appended here so it is never re-rolled (default "
                             "config/used_seeds.json)")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"publish_battle: video not found: {video}")

    events = load_json(args.events)
    stats_file = Path(args.stats)
    publish_root = Path(args.publish)
    song_dir = publish_root / args.song

    # Leaderboard.
    stats = load_json(stats_file)
    battle_num = int(stats.get("battle_count", 0)) + 1

    positions = finishing_positions(events)
    points = battle_points(positions)

    # Move the video into the publish folder (it's leaving the renders folder).
    song_dir.mkdir(parents=True, exist_ok=True)
    out_video = song_dir / f"battle_{battle_num:03d}.mp4"
    shutil.move(str(video), str(out_video))

    metadata = {
        "battle": battle_num,
        "season": SEASON,
        "track": args.song,
        "seed": events.get("seed"),
        "duration_s": events.get("duration_s"),
        "winner": int(events["winner"]["ball_id"]),
        "positions": positions,
        "points": points,
        "stats": events.get("stats", {}),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(song_dir / f"battle_{battle_num:03d}.json", metadata)

    # Update the leaderboard.
    stats["battle_count"] = battle_num
    for ball in stats["balls"]:
        bid = ball["id"]
        pos = positions.get(bid)
        if pos is None:
            continue
        ball["points"] = ball.get("points", 0) + POINTS[pos]
        ball["total_battles"] = ball.get("total_battles", 0) + 1
        if pos == 1:
            ball["wins"] = ball.get("wins", 0) + 1
        else:
            ball["losses"] = ball.get("losses", 0) + 1
        if pos <= 3:
            ball["podiums"] = ball.get("podiums", 0) + 1
        bstats = events.get("stats", {}).get(str(bid), {})
        ball["kills"] = ball.get("kills", 0) + bstats.get("kills", 0)
        ball["eliminations"] = ball.get("eliminations", 0) + bstats.get("kills", 0)
        ball["collisions"] = ball.get("collisions", 0) + bstats.get("collisions", 0)
    save_json(stats_file, stats)

    # Record the battle's seed so a future simulate never re-rolls the same
    # battle (deterministic sim -> same battle).
    seed = events.get("seed")
    if seed is not None and record_seed(int(seed), args.used_seeds):
        print(f"recorded seed {seed} in {args.used_seeds}")

    # Prune to --max per song (keep the newest).
    videos = sorted(song_dir.glob("battle_*.mp4"))
    for old in videos[:-args.max] if len(videos) > args.max else []:
        old.unlink()
        old.with_suffix(".json").unlink(missing_ok=True)

    print(f"published {out_video}")
    print(f"winner: {metadata['winner']}  points: {points}  duration: {metadata['duration_s']}s")
    print("\nLEADERBOARD (points):")
    for ball in sorted(stats["balls"], key=lambda b: -b.get("points", 0)):
        if ball.get("total_battles", 0) > 0:
            print(f"  {ball['name']:8s} {ball.get('points', 0):3d} pts  "
                  f"{ball.get('wins', 0)}W {ball.get('podiums', 0)} podiums")


if __name__ == "__main__":
    main()
