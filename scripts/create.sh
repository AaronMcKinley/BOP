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
# Usage: ./scripts/create.sh <song> [event_chance]
#   song (required): path to the song file, e.g. "songs/cradles.mp3"
#   event_chance (optional, 0..1): probability a random battle event fires
#   (immunity / speed boost). Default 0 = no random events; sudden death at
#   1:30 is always on as the battle backstop.
#   e.g. ./scripts/create.sh "songs/cradles.mp3"
#   e.g. ./scripts/create.sh "songs/cradles.mp3" 0.5
#        -> 50% chance of an event
#
#   Render resolution via RES: default 1080x1920 (crisp Full HD - the current
#   540x960 source was getting upscaled and looked soft after platform
#   re-encoding). RES=2160x3840 for 4K (much slower, bigger files).
#
#   Song selection via SONG env instead of the first argument:
#   e.g. SONG="songs/shine.mp3" ./scripts/create.sh
#   The song's timeline (output/timelines/<song>.json) drives the energy speed
#   ramp and drop detection - run analysis/analyze.py on it first:
#     .venv/bin/python analysis/analyze.py "songs/shine.mp3" \
#         --out output/timelines/shine.json

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Song is required (first argument or SONG env) - the script never guesses one.
SONG="${1:-${SONG:-}}"
if [ -z "$SONG" ]; then
  echo "usage: ./scripts/create.sh <song> [event_chance]"
  echo "  e.g. ./scripts/create.sh \"songs/cradles.mp3\""
  exit 1
fi
# Accept a bare filename too: "cradles.mp3" -> songs/cradles.mp3
# (also accepts "songs/cradles.mp3" or an absolute path).
if [ ! -f "$SONG" ] && [ -f "$ROOT/songs/$(basename "$SONG")" ]; then
  SONG="$ROOT/songs/$(basename "$SONG")"
fi
if [ ! -f "$SONG" ]; then
  echo "error: song file not found: $SONG"
  echo "  put the music in songs/ and pass \"songs/<file>\" or just \"<file>\""
  exit 1
fi
# event_chance: second argument (or EVENT_CHANCE env, default 0 = none).
EVENT_CHANCE="${2:-${EVENT_CHANCE:-0}}"
RES="${RES:-1080x1920}"
BALLS="${BALLS:-5}"
MIN_DURATION="${MIN_DURATION:-45}"
SONG_BASE="$(basename "$SONG")"
# Clean song name for the timeline + publish folder: strip the extension and
# turn spaces/brackets into dashes. e.g. "shine.mp3" -> "shine".
SONG_NAME="$(printf '%s' "${SONG_BASE%.*}" | tr -cs '[:alnum:]' '-')"
SONG_NAME="${SONG_NAME%%-}"

# Make sure the song's credit file exists (config/credits/<song>.txt). Fill in
# the required music credit before saving - save.py reads it for the caption.
CREDIT_FILE="$ROOT/config/credits/${SONG_NAME}.txt"
mkdir -p "$ROOT/config/credits"
if [ ! -f "$CREDIT_FILE" ]; then
  touch "$CREDIT_FILE"
fi

TIMELINE="$ROOT/output/timelines/${SONG_NAME}.json"
EVENTS="$ROOT/output/events/current.json"
AVI="$ROOT/output/renders/current.avi"
MP4="$ROOT/output/renders/current.mp4"
SONG_FILE="$ROOT/output/events/song.txt"

# Fresh output every run - no stale files.
rm -f "$EVENTS" "$AVI" "$MP4" "$SONG_FILE"

# Record which song this battle belongs to - save.py reads this (it has no
# song default of its own), so the publish folder always matches the music.
printf '%s' "$SONG_NAME" > "$SONG_FILE"

# The timeline IS the analysis: it drives the battle pacing (simulate), the
# arena pulsing and the spoke rotation (render). Required - no fallback or
# default: if the song hasn't been analysed the pipeline fails and says what
# to run.
if [ ! -f "$TIMELINE" ]; then
  echo "error: no timeline for this song: $TIMELINE"
  echo "  analyse it first with:"
  echo "    .venv/bin/python analysis/analyze.py \"$SONG\" --out \"$TIMELINE\""
  exit 1
fi

echo "== simulating battle (song: ${SONG_NAME}, event chance ${EVENT_CHANCE}) =="
.venv/bin/python simulation/simulate.py --balls "$BALLS" --min-duration "$MIN_DURATION" \
  --event-chance "$EVENT_CHANCE" --timeline "$TIMELINE" --out "$EVENTS"

echo "== rendering at ${RES} (a window flashes; length = battle length) =="
# The renderer gets the same timeline: the arena rim bumps on this song's
# beats, the shockwaves follow its energy, and the spokes rotate one full turn
# per beat - never the fixture's.
flatpak run org.godotengine.Godot --path "$ROOT/render" --resolution "$RES" \
  --write-movie "$AVI" --quit-after 20000 --fixed-fps 60 \
  -- --events "$EVENTS" --timeline "$TIMELINE"

echo "== muxing with music (song: ${SONG_NAME}) =="
.venv/bin/python postprocess/mux.py --video "$AVI" --audio "$SONG" --out "$MP4"

echo "== playing $MP4 =="
xdg-open "$MP4"
