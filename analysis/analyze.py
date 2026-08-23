"""analyze.py: assemble timeline.json from a song file.

Combines beat detection, energy analysis and section detection into the
timeline.json data contract (see README). Section boundaries are snapped to
the nearest beat so the crescendo lands on the grid.

Note: this loads the audio twice (once in extract_beats, once in extract_energy).
That is a few extra seconds and keeps the two extractors independently usable.

Usage:
  python analysis/analyze.py songs/track.wav --out output/timelines/track.json
"""

import argparse
import json
from pathlib import Path

import numpy as np

from beat_detect import extract_beats
from energy import extract_energy

SMOOTH_WINDOW_S = 1.0    # moving-average window for the energy curve (s)
DROP_FLOOR = 0.45        # drop extends from the peak while energy stays above this fraction of peak
INTRO_THRESHOLD = 0.4    # intro ends once energy sustains above this fraction of peak
INTRO_SUSTAIN_S = 3.0    # how long energy must stay above the intro threshold (s)
MIN_DROP_S = 4.0         # minimum credible drop length (s)


def _snap_to_beat(t: float, beats: list) -> float:
    """Return the nearest beat time to t (or t unchanged if there are no beats)."""
    if not beats:
        return t
    idx = int(np.searchsorted(beats, t))
    candidates = []
    if idx > 0:
        candidates.append(beats[idx - 1])
    if idx < len(beats):
        candidates.append(beats[idx])
    return float(min(candidates, key=lambda b: abs(b - t)))


def detect_sections(energy_curve: list, beats: list, duration_s: float) -> list:
    """Return [{label, start, end}] for intro / build / drop / resolution.

    Heuristic (all tunable at the top of this file):
      * drop = the high-energy region grown outward from the global energy peak
        while the smoothed energy stays above DROP_FLOOR of the peak
      * intro = the calm opening, ends once energy has sustained above
        INTRO_THRESHOLD of the peak for INTRO_SUSTAIN_S
      * build = between intro and drop
      * resolution = everything after the drop
    Boundaries are snapped to the nearest beat.
    """
    times = np.array([t for t, _ in energy_curve])
    energy = np.array([e for _, e in energy_curve])
    win = max(1, int(SMOOTH_WINDOW_S * 10))
    smoothed = np.convolve(energy, np.ones(win) / win, mode="same")

    peak = float(smoothed.max()) if smoothed.size else 1.0
    if peak <= 0:
        peak = 1.0
    min_run = max(1, int(MIN_DROP_S * 10))

    # Drop: grow outward from the global energy peak while energy stays above
    # the floor. This is more robust than "longest run above a threshold",
    # which fragments around brief dips between phrases.
    center = int(np.argmax(smoothed))
    floor = DROP_FLOOR * peak
    best_start = center
    while best_start > 0 and smoothed[best_start - 1] >= floor:
        best_start -= 1
    best_end = center
    while best_end < len(smoothed) - 1 and smoothed[best_end + 1] >= floor:
        best_end += 1

    # Intro ends once energy has sustained above a fraction of the peak for a
    # few seconds. A single early hit shouldn't end the intro.
    intro_thresh = INTRO_THRESHOLD * peak
    sustain_n = max(1, int(INTRO_SUSTAIN_S * 10))
    intro_end_i = 0
    streak = 0
    for i, e in enumerate(smoothed):
        if e >= intro_thresh:
            streak += 1
            if streak >= sustain_n:
                intro_end_i = i
                break
        else:
            streak = 0

    # Keep the section indices ordered: intro <= build <= drop start < drop end.
    intro_end_i = min(intro_end_i, best_start)
    build_start_i = min(max(intro_end_i + 1, best_start), len(smoothed) - 1)
    drop_start_i = max(build_start_i, best_start)
    drop_end_i = max(drop_start_i + min_run, best_end)
    drop_end_i = min(drop_end_i, len(smoothed) - 1)

    raw = [
        ("intro", 0, intro_end_i),
        ("build", intro_end_i, drop_start_i),
        ("drop", drop_start_i, drop_end_i),
        ("resolution", drop_end_i, len(smoothed) - 1),
    ]

    sections = []
    for label, start_i, end_i in raw:
        start_t = float(times[start_i])
        end_t = float(times[min(end_i, len(times) - 1)])
        if label != "intro":
            start_t = _snap_to_beat(start_t, beats)
        if label != "resolution":
            end_t = _snap_to_beat(end_t, beats)
        # Keep sections ordered and inside the song.
        if sections:
            start_t = max(start_t, sections[-1]["end"])
        end_t = max(end_t, start_t)
        end_t = min(end_t, duration_s)
        if end_t > start_t:
            sections.append({
                "label": label,
                "start": round(start_t, 3),
                "end": round(end_t, 3),
            })

    return sections


def analyze_song(audio_path: str, sr: int = 22050) -> dict:
    """Return the full timeline.json dict for the audio file."""
    beats_data = extract_beats(audio_path, sr=sr)
    energy_data = extract_energy(audio_path, sr=sr)

    duration_s = round(float(energy_data["energy_curve"][-1][0]), 3)
    sections = detect_sections(energy_data["energy_curve"], beats_data["beats"], duration_s)

    return {
        "duration_s": duration_s,
        "bpm": beats_data["tempo"],
        "beats": beats_data["beats"],
        "downbeats": beats_data["downbeats"],
        "energy_curve": energy_data["energy_curve"],
        "bass_hits": energy_data["bass_hits"],
        "sections": sections,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build timeline.json from a song file.")
    parser.add_argument("audio", type=str, help="path to the audio file")
    parser.add_argument("--out", type=str, default=None,
                        help="output path for timeline.json (prints summary if omitted)")
    parser.add_argument("--sr", type=int, default=22050, help="analysis sample rate (default 22050)")
    args = parser.parse_args()

    timeline = analyze_song(args.audio, sr=args.sr)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(timeline, indent=1), encoding="utf-8")
        print(f"wrote {out}")

    print(f"duration: {timeline['duration_s']}s  bpm: {timeline['bpm']}  "
          f"beats: {len(timeline['beats'])}  bass_hits: {len(timeline['bass_hits'])}")
    for s in timeline["sections"]:
        print(f"  {s['label']:10s} {s['start']:8.2f}s -> {s['end']:8.2f}s")
