#!/usr/bin/env bash
# create.sh: run a fresh battle end-to-end and play the result.
#
#   simulate (fresh unused seed) -> Godot render -> mux with music -> play
#
# The video length is the battle length (it runs until one ball remains, plus
# the winner screen). The window flashes during the render - Movie Maker needs
# a real display.
#
# If you like the battle, save it afterwards with:
#   python scripts/save.py
# (moves it to the publish folder, updates stats, records the seed).
#
# Usage: ./scripts/create.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SONG="$ROOT/songs/MONODY-BIMONTE-REMIX.wav"
SONG_NAME="$(basename "$SONG" .wav)"
EVENTS="$ROOT/output/events/current.json"
AVI="$ROOT/output/renders/current.avi"
MP4="$ROOT/output/renders/current.mp4"

# Fresh output every run - no stale files.
rm -f "$EVENTS" "$AVI" "$MP4"

echo "== simulating battle (fresh random seed, re-rolling until >= 45s) =="
.venv/bin/python simulation/simulate.py --balls 5 --min-duration 45 --out "$EVENTS"

echo "== rendering (a window flashes; length = battle length) =="
flatpak run org.godotengine.Godot --path "$ROOT/render" --resolution 540x960 \
  --write-movie "$AVI" --quit-after 20000 --fixed-fps 60 \
  -- --events "$EVENTS"

echo "== muxing with music =="
.venv/bin/python postprocess/mux.py --video "$AVI" --audio "$SONG" --out "$MP4"

echo "== playing $MP4 =="
xdg-open "$MP4"
