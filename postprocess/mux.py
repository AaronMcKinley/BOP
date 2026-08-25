"""mux.py: combine a rendered Godot video with the original song.

This is the minimal postprocess step: upscale the small render to the
platform-native 1080x1920, encode as H.264/AAC, and mux the song. Full
platform presets and loudness normalization come later.

Usage:
  python postprocess/mux.py --video output/renders/r3_ring.avi \
      --audio "songs/MONODY-BIMONTE-REMIX.wav" \
      --out output/renders/r3_ring.mp4
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920   # platform-native short-form size
# The render appends the end sequence (winner reveal + league table) after the
# battle. The music fade starts when that sequence begins. END_SEQ_S must match
# TOTAL_S in render/scripts/winner_screen.gd.
END_SEQ_S = 8.5
FADE_S = 6.0                 # audio taper length (runs over the end sequence)

# Faint background watermark (brand mark) applied during the final encode.
WATERMARK_DEFAULT = "BOP - Beat-Orientated-Physics"   # empty string disables
WATERMARK_ALPHA = 0.22       # opacity 0..1 - subtle, sits in the background
WATERMARK_COLOR = "0x9FF0FF" # light neon cyan to match the brand
WATERMARK_SIZE = 44
WATERMARK_Y = 1500           # below the arena circle, in the dark bottom border


def _video_duration(path: Path) -> float:
    """Duration of the rendered video (seconds), for the audio fade timing."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _nearest_lull(song_t: float, energy_curve: list, window: float = 3.0) -> float:
    """Time of the quietest energy sample within +/-window seconds of song_t.

    Used for the break-based ending: the music fades into a natural dip near
    the winner screen instead of a fixed taper. Falls back to song_t itself if
    no timeline is given (the curve is empty)."""
    best_t, best_e = song_t, None
    for t, e in energy_curve:
        if abs(t - song_t) <= window:
            if best_e is None or e < best_e:
                best_e, best_t = e, t
    return best_t


def mux(video: Path, audio: Path, out: Path, offset_s: float = 0.0,
        watermark: str = WATERMARK_DEFAULT,
        watermark_alpha: float = WATERMARK_ALPHA,
        timeline_path: str = "") -> None:
    """Upscale the video, encode it, and mux the song starting at offset_s.

    watermark is faint brand text drawn on the frame background ('' = none).
    timeline_path (optional) is the song's timeline.json; its energy curve is
    used for a break-based ending - the music fades into a quiet lull near the
    winner screen instead of a fixed taper.
    """
    if not video.exists():
        sys.exit(f"mux: video not found: {video}")
    if not audio.exists():
        sys.exit(f"mux: audio not found: {audio}")
    out.parent.mkdir(parents=True, exist_ok=True)

    # `-ss` placed before `-i audio` seeks that input, so the video can start
    # at any point in the song (the director will pick a highlight window later).
    audio_args = ["-ss", str(offset_s)] if offset_s > 0 else []

    # Fade the music out over the end sequence (winner screen) instead of
    # cutting it hard. When the song's timeline is given, the fade lands on a
    # detected lull so the winner screen sits in a natural dip.
    duration = _video_duration(video)
    afilter = None
    if duration > FADE_S + 1.0:
        fade_start = max(0.0, duration - END_SEQ_S)
        if timeline_path:
            try:
                with open(timeline_path, encoding="utf-8") as f:
                    energy_curve = json.load(f).get("energy_curve", [])
            except (OSError, json.JSONDecodeError):
                energy_curve = []
            if energy_curve:
                song_at_win = offset_s + (duration - END_SEQ_S)
                lull = _nearest_lull(song_at_win, energy_curve)
                fade_start = max(0.0, min(duration - 1.0, lull - offset_s - FADE_S * 0.5))
        afilter = f"afade=t=out:st={fade_start:.2f}:d={FADE_S}:curve=esin"

    # Upscale, then lay the faint watermark in the background below the arena
    # circle - visible but not competing with the action or the winner screen.
    vfilter = f"scale={WIDTH}:{HEIGHT}:flags=lanczos"
    if watermark:
        vfilter += (
            f",drawtext=text='{watermark}':fontcolor={WATERMARK_COLOR}@{watermark_alpha}"
            f":fontsize={WATERMARK_SIZE}:x=(w-text_w)/2:y={WATERMARK_Y}")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        *audio_args, "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",   # only video from the render, only audio from the song
        "-vf", vfilter,
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        *(["-af", afilter] if afilter else []),
        "-shortest",
        str(out),
    ]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"mux: ffmpeg failed:\n{result.stderr}")
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mux rendered video with the original song.")
    parser.add_argument("--video", required=True, help="rendered video (e.g. output/renders/x.avi)")
    parser.add_argument("--audio", required=True, help="original song file")
    parser.add_argument("--out", required=True, help="output mp4 path")
    parser.add_argument("--offset", type=float, default=0.0,
                        help="seconds into the song where the video begins (default 0)")
    parser.add_argument("--watermark", default=WATERMARK_DEFAULT,
                        help=f"faint brand text on the frame background ('' disables; "
                             f"default '{WATERMARK_DEFAULT}')")
    parser.add_argument("--watermark-alpha", type=float, default=WATERMARK_ALPHA,
                        help="watermark opacity 0..1 (default 0.22)")
    parser.add_argument("--timeline", type=str, default="",
                        help="song timeline.json; its energy curve puts the end fade "
                             "into a natural lull (break-based ending)")
    args = parser.parse_args()

    mux(Path(args.video), Path(args.audio), Path(args.out), args.offset,
        args.watermark, args.watermark_alpha, args.timeline)
