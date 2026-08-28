#!/usr/bin/env python3
"""save.py: save the last created battle (video + events + stats).

The create script (scripts/create.sh) leaves its outputs at
output/renders/current.mp4 and output/events/current.json. Running this with
no arguments picks those up, moves the video into
output/publish/<song>/battle_<n>.mp4 (auto-incremented, never overwrites),
writes battle_<n>.json metadata, updates the season leaderboard
(config/stats.json), and records the seed in config/used_seeds.json so the
same battle is never created again.

Usage:
  python scripts/save.py                # save the last created battle
  python scripts/save.py --song OTHER   # publish under a different song name
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.scoring import POINTS, battle_points, finishing_positions
from simulation.seed_registry import (
    DEFAULT_PATH as USED_SEEDS_FILE,
    load_used_seeds,
    record_seed,
)

STATS_FILE = ROOT / "config" / "stats.json"
PUBLISH_ROOT = ROOT / "output" / "publish"
DEFAULT_VIDEO = ROOT / "output" / "renders" / "current.mp4"
DEFAULT_EVENTS = ROOT / "output" / "events" / "current.json"
# The song is whatever create.sh last used (it writes the name here) - save.py
# has no song default of its own, so the publish folder always matches the music.
SONG_FILE = ROOT / "output" / "events" / "song.txt"
# The most recent saved battle's metadata path - undo_save.py defaults to it.
LAST_SAVED_FILE = ROOT / "output" / "events" / "last_saved.txt"
# Plain-text per-song credit lines, config/credits/<song>.txt (the caption).
CREDITS_DIR = ROOT / "config" / "credits"
DEFAULT_MAX_PER_SONG = 10
SEASON = 1


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_credit(song: str) -> str:
    """The song's required music credit, from config/credits/<song>.txt."""
    try:
        return (CREDITS_DIR / f"{song}.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_caption(metadata: dict, credit: str, stats: dict) -> str:
    """A ready-to-paste caption for the saved battle, including the song's
    license credit (each platform wants the required credit in the description)."""
    wid = int(metadata["winner"])
    name = next((b["name"] for b in stats["balls"] if b["id"] == wid), "???")
    dur = metadata.get("duration_s", 0)
    points = metadata.get("points", {})
    # battle_points() keys are ints in memory (strings after the JSON round-trip).
    delta = int(points.get(wid, points.get(str(wid), 0)))
    total = next((b.get("points", 0) for b in stats["balls"] if b["id"] == wid), 0)
    lines = [
        f"{name.upper()} WINS! 🏆",
        f"seed #{metadata.get('seed', '?')} · {dur}s",
        "",
        "New battle every day — Season 1: the Neon League.",
    ]
    if delta or total:
        lines.append(f"Scoreboard: +{delta} = {total}")
    if credit:
        lines.append("")
        lines.append(credit)
    lines.append("")
    lines.append("#BOP #BeatOrientatedPhysics #neon #shorts")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Save the last created battle to the publish folder + update stats.")
    parser.add_argument("--video", default=str(DEFAULT_VIDEO),
                        help="rendered mp4 (default output/renders/current.mp4)")
    parser.add_argument("--events", default=str(DEFAULT_EVENTS),
                        help="events.json for this battle (default output/events/current.json)")
    parser.add_argument("--song", default=None,
                        help="song name for the publish folder (default: the song "
                             "create.sh last used, from output/events/song.txt)")
    parser.add_argument("--stats", default=str(STATS_FILE),
                        help="leaderboard json path (default config/stats.json)")
    parser.add_argument("--publish", default=str(PUBLISH_ROOT),
                        help="publish root folder (default output/publish)")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_PER_SONG,
                        help="keep only this many newest videos per song (default 10)")
    parser.add_argument("--used-seeds", type=str, default=str(USED_SEEDS_FILE),
                        help="json list of seeds already used; the battle's seed is "
                             "appended here so it is never created again "
                             "(default config/used_seeds.json)")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"save: video not found: {video}\nRun scripts/create.sh first.")
    events_path = Path(args.events)
    if not events_path.exists():
        sys.exit(f"save: events not found: {events_path}\nRun scripts/create.sh first.")

    events = load_json(events_path)

    # The song comes from create.sh (it wrote the name to song.txt); --song is
    # only an override. No default of its own, so it always matches the music.
    song = args.song
    if song is None:
        try:
            song = SONG_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            sys.exit(f"save: no song on record (missing {SONG_FILE}).\n"
                     f"Run scripts/create.sh first - it writes the song name there.")
    if not song:
        sys.exit("save: empty song name in " + str(SONG_FILE))

    # Never save the same battle twice: the seed makes the sim deterministic,
    # so saving it again would double-count the stats.
    seed = events.get("seed")
    if seed is not None and int(seed) in load_used_seeds(args.used_seeds):
        sys.exit(f"save: seed {seed} was already saved (see {args.used_seeds}) - duplicate battle.")

    stats_file = Path(args.stats)
    publish_root = Path(args.publish)
    song_dir = publish_root / song

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
        "track": song,
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

    # Ready-to-paste caption for the published battle, with the song's required
    # music credit baked in (from config/credits/<song>.txt).
    caption = build_caption(metadata, load_credit(song), stats)
    (song_dir / f"battle_{battle_num:03d}_caption.txt").write_text(caption, encoding="utf-8")

    # Record the battle's seed so a future create never rolls the same battle.
    if seed is not None and record_seed(int(seed), args.used_seeds):
        print(f"recorded seed {seed} in {args.used_seeds}")

    # Remember which battle was just saved, so undo_save.py can default to it
    # (it is always the most recent one you would want to undo).
    LAST_SAVED_FILE.write_text(str(song_dir / f"battle_{battle_num:03d}.json"),
                               encoding="utf-8")

    # Prune to --max per song (keep the newest).
    videos = sorted(song_dir.glob("battle_*.mp4"))
    for old in videos[:-args.max] if len(videos) > args.max else []:
        old.unlink()
        old.with_suffix(".json").unlink(missing_ok=True)

    print(f"saved {out_video}")
    print(f"winner: {metadata['winner']}  points: {points}  duration: {metadata['duration_s']}s")
    print("\nLEADERBOARD (points):")
    for ball in sorted(stats["balls"], key=lambda b: -b.get("points", 0)):
        if ball.get("total_battles", 0) > 0:
            print(f"  {ball['name']:8s} {ball.get('points', 0):3d} pts  "
                  f"{ball.get('wins', 0)}W {ball.get('podiums', 0)} podiums")


if __name__ == "__main__":
    main()

