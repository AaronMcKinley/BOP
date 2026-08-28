#!/usr/bin/env python3
"""undo_save.py: unpublish a saved battle - a mistake-recovery inverse of save.py.

Usage:
  python scripts/undo_save.py                        # undo the most recent save
  python scripts/undo_save.py output/publish/cradles/battle_003.json
  python scripts/undo_save.py <path> --dry-run

With no argument it reads output/events/last_saved.txt (written by save.py) and
undoes that battle - it is always the most recent save. Given the battle's
publish metadata json, it:
  * deletes the battle's files (mp4 + json + caption), then the song folder
    if that empties it
  * forgets the seed in config/used_seeds.json (so the battle can be made again)
  * reverses everything save.py added to config/stats.json

--dry-run prints what it would do without changing anything.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.seed_registry import DEFAULT_PATH as USED_SEEDS_FILE  # noqa: E402

STATS_FILE = ROOT / "config" / "stats.json"
PUBLISH_ROOT = (ROOT / "output" / "publish").resolve()
LAST_SAVED_FILE = ROOT / "output" / "events" / "last_saved.txt"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Unpublish a saved battle: delete its files, forget its seed, "
                    "and reverse its stats.")
    parser.add_argument("metadata", nargs="?", default=None, type=str,
                        help="path to the battle's publish metadata, e.g. "
                             "output/publish/cradles/battle_003.json "
                             "(default: the most recent save, from "
                             "output/events/last_saved.txt)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would change without touching anything")
    parser.add_argument("--stats", default=str(STATS_FILE),
                        help="leaderboard json path (default config/stats.json)")
    parser.add_argument("--used-seeds", type=str, default=str(USED_SEEDS_FILE),
                        help="json list of used seeds (default config/used_seeds.json)")
    args = parser.parse_args()

    # No path given -> undo the most recent save (save.py records it here).
    if args.metadata is None:
        try:
            recorded = LAST_SAVED_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            recorded = ""
        if not recorded:
            sys.exit("undo: no last saved battle on record.\n"
                     "Run save.py first, or pass the battle json path explicitly.")
        args.metadata = recorded

    meta_path = Path(args.metadata).resolve()
    if PUBLISH_ROOT not in meta_path.parents:
        sys.exit(f"undo: {meta_path} is not inside {PUBLISH_ROOT}")
    if not meta_path.is_file():
        sys.exit(f"undo: metadata not found: {meta_path}")

    meta = load_json(meta_path)
    battle_num = int(meta.get("battle", 0))
    seed = meta.get("seed")
    song_dir = meta_path.parent
    base = meta_path.stem
    dry = " (dry run - nothing changed)" if args.dry_run else ""

    # --- 1. forget the seed ----------------------------------------------------
    seeds_path = Path(args.used_seeds)
    seeds = load_json(seeds_path) if seeds_path.exists() else []
    if seed in seeds:
        if not args.dry_run:
            save_json(seeds_path, [s for s in seeds if s != seed])
        print(f"removed seed {seed} from {seeds_path}{dry}")
    else:
        print(f"note: seed {seed} was not in {seeds_path}")

    # --- 2. reverse the leaderboard stats --------------------------------------
    stats = load_json(args.stats)
    positions = meta.get("positions", {})
    points = meta.get("points", {})
    bstats = meta.get("stats", {})
    for ball in stats["balls"]:
        bid = ball["id"]
        pos = positions.get(str(bid))
        if pos is None:
            continue
        bs = bstats.get(str(bid), {})
        kills = bs.get("kills", 0)
        old = {key: ball.get(key, 0) for key in
               ("points", "total_battles", "wins", "losses", "podiums",
                "kills", "eliminations", "collisions")}
        new = {
            "points": old["points"] - points.get(str(bid), 0),
            "total_battles": old["total_battles"] - 1,
            "wins": old["wins"] - (1 if pos == 1 else 0),
            "losses": old["losses"] - (0 if pos == 1 else 1),
            "podiums": old["podiums"] - (1 if pos <= 3 else 0),
            "kills": old["kills"] - kills,
            "eliminations": old["eliminations"] - kills,  # save.py adds kills
            "collisions": old["collisions"] - bs.get("collisions", 0),
        }
        if not args.dry_run:
            for key, val in new.items():
                ball[key] = max(0, val)
        print(f"  {ball['name']:6s} pts {old['points']}->{new['points']} "
              f"tb {old['total_battles']}->{new['total_battles']}{dry}")
    # Only rewind the counter when removing the newest battle, so a battle number
    # is never reused (undoing an older battle leaves a gap instead).
    if int(stats.get("battle_count", 0)) == battle_num:
        if not args.dry_run:
            stats["battle_count"] = battle_num - 1
        print(f"battle_count {battle_num} -> {battle_num - 1}{dry}")
    if not args.dry_run:
        save_json(args.stats, stats)

    # --- 3. delete the battle's files, then the song folder if it empties -------
    for f in (song_dir / f"{base}.mp4", song_dir / f"{base}.json",
              song_dir / f"{base}_caption.txt"):
        if f.exists():
            if not args.dry_run:
                f.unlink()
            print(f"deleted {f}{dry}")
    if not args.dry_run and song_dir.exists() and not any(song_dir.iterdir()):
        song_dir.rmdir()
        print(f"removed empty folder {song_dir}")

    print(f"unpublished {song_dir.name} battle_{battle_num:03d}{dry}")

    # If the undone battle was the recorded most-recent save, clear the marker
    # so the next no-arg undo doesn't point at a deleted battle.
    if not args.dry_run:
        try:
            recorded = LAST_SAVED_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            recorded = ""
        if recorded and Path(recorded).resolve() == meta_path:
            LAST_SAVED_FILE.write_text("", encoding="utf-8")
            print(f"cleared last-saved marker ({LAST_SAVED_FILE})")


if __name__ == "__main__":
    main()
