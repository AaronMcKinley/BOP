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
import subprocess
import sys
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920   # platform-native short-form size


def mux(video: Path, audio: Path, out: Path, offset_s: float = 0.0) -> None:
    """Upscale the video, encode it, and mux the song starting at offset_s."""
    if not video.exists():
        sys.exit(f"mux: video not found: {video}")
    if not audio.exists():
        sys.exit(f"mux: audio not found: {audio}")
    out.parent.mkdir(parents=True, exist_ok=True)

    # `-ss` placed before `-i audio` seeks that input, so the video can start
    # at any point in the song (the director will pick a highlight window later).
    audio_args = ["-ss", str(offset_s)] if offset_s > 0 else []

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        *audio_args, "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",   # only video from the render, only audio from the song
        "-vf", f"scale={WIDTH}:{HEIGHT}:flags=lanczos",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
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
    args = parser.parse_args()

    mux(Path(args.video), Path(args.audio), Path(args.out), args.offset)
