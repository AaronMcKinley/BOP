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
INTRO_THRESHOLD = 0.4    # intro ends once energy sustains above this fraction of peak
INTRO_SUSTAIN_S = 3.0    # how long energy must stay above the intro threshold (s)
MIN_DROP_S = 4.0         # minimum credible drop length (s)

# Drop detection: a drop is a sharp phrase-scale surge that lands at high
# energy, measured relative to THIS song. The main drop is the surge with the
# deepest calm->storm climb in the song's usual drop range, and the drop
# section starts where that climb begins (the trough).
DROP_WINDOW_S = 6.0      # phrase-scale window for a drop's rise
DROP_MIN_GAP_S = 10.0    # keep qualifying surges apart
DROP_RISE_PCT = 90.0     # a surge's rise must beat 90% of this song's rises
DROP_LAND_PCT = 80.0     # ... and land in the top 20% of its energy
DROP_SELECT_LIMIT_S = 70.0  # the drop lives in the song's usual 40s-1:10 range
TROUGH_LOOKBACK_S = 8.0  # how far before a surge to hunt for the calm trough
DROP_SUSTAIN_S = 10.0    # how far ahead to score a surge's sustained level
DROP_CLIMB_FRAC = 0.35   # the drop "hits" once the climb is 35% underway


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
      * drop = the sharp phrase-scale surge with the deepest calm->storm climb
        in the song's usual drop range (40s-1:10). The drop section starts at
        the trough where that climb begins - the moment the listener hears
        "here it comes".
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

    # --- Intro: the calm opening. ---
    # Ends once energy has sustained above a fraction of the peak for a few
    # seconds. A single early hit shouldn't end the intro.
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

    # --- Drop: the main musical drop moment. ---
    # Find the qualifying phrase-scale surges (rise + landing relative to this
    # song) AFTER the intro, then the main drop is the one with the deepest
    # trough->landing climb. The drop section starts at that trough.
    dt = max(times[1] - times[0], 0.001) if times.size > 1 else 0.1
    n = max(1, int(round(DROP_WINDOW_S / dt)))
    rises = smoothed[n:] - smoothed[:-n]
    lands = smoothed[n:]
    pos = rises[rises > 0]
    rise_thresh = float(np.percentile(pos, DROP_RISE_PCT)) if pos.size else 0.0
    land_thresh = float(np.percentile(lands, DROP_LAND_PCT))

    surge_idx = []
    last = -DROP_MIN_GAP_S
    for i in range(n, len(smoothed)):
        t = times[i]
        if t > DROP_SELECT_LIMIT_S:
            break
        if t - last >= DROP_MIN_GAP_S and rises[i - n] >= rise_thresh \
                and lands[i - n] >= land_thresh:
            surge_idx.append(i)
            last = t

    drop_start_i = drop_end_i = len(smoothed) - 1   # no qualifying drop
    if surge_idx:
        best_score, best = -1.0, None
        sustain_n = max(1, int(round(DROP_SUSTAIN_S / dt)))
        for i in surge_idx:
            # The drop is the surge that enters the *highest sustained* section:
            # score each by its average energy over the next ~DROP_SUSTAIN_S.
            window = smoothed[i:i + sustain_n]
            score = float(window.mean()) if window.size else 0.0
            if score > best_score:
                best_score, best = score, i
        if best is not None:
            # Drop start: the calm trough just before that landing, then advance
            # to where the climb is genuinely underway - the moment the listener
            # hears the hit (trough bottom is ~2s too early).
            lookback = max(1, int(round(TROUGH_LOOKBACK_S / dt)))
            j = max(0, best - lookback)
            trough_idx = j + int(np.argmin(smoothed[j:best + 1]))
            target = smoothed[trough_idx] + DROP_CLIMB_FRAC \
                * (smoothed[best] - smoothed[trough_idx])
            hit = trough_idx
            while hit < best and smoothed[hit] < target:
                hit += 1
            if hit > intro_end_i:
                drop_start_i = hit
            # Drop end: the sustained high run it entered (forgiving floor so a
            # single-sample dip doesn't end it).
            drop_end_i = best
            floor = land_thresh * 0.85
            while drop_end_i < len(smoothed) - 1 and smoothed[drop_end_i + 1] >= floor:
                drop_end_i += 1

    # Keep the section indices ordered: intro <= build <= drop start < drop end.
    intro_end_i = min(intro_end_i, drop_start_i)
    build_start_i = min(max(intro_end_i + 1, drop_start_i), len(smoothed) - 1)
    drop_start_i = max(build_start_i, drop_start_i)
    drop_end_i = max(drop_start_i + min_run, drop_end_i)
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
