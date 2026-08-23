"""Beat detection: audio file -> tempo, beats, downbeats.

This is the first stage of analysis. Later, analyze.py assembles these values
into timeline.json (the full data contract).

librosa 1.0 notes:
  * librosa.beat.beat_track() returns `tempo` as a 1-element numpy array,
    not a scalar - unwrap it with np.asarray(tempo).item().
  * librosa has no built-in downbeat detector. We assume 4/4 time and take
    every 4th beat from the first detected beat, which is a good fit for
    EDM-style tracks. This can be refined later if needed.
"""

import argparse
from pathlib import Path
from typing import Dict, List, Union

import librosa
import numpy as np

DEFAULT_SR = 22050


def extract_beats(audio_path: Union[str, Path], sr: int = DEFAULT_SR) -> Dict[str, object]:
    """Return a dict with tempo (bpm), beat times (s), and downbeat times (s).

    Values are rounded so the result is directly JSON-serializable for timeline.json.
    """
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.asarray(tempo).item())

    beats = librosa.frames_to_time(beat_frames, sr=sr).astype(float)
    downbeats = beats[0::4].astype(float)  # 4/4 assumption

    return {
        "tempo": round(tempo, 2),
        "beats": [round(float(t), 6) for t in beats],
        "downbeats": [round(float(t), 6) for t in downbeats],
    }


def _print_summary(result: Dict[str, object]) -> None:
    """Human-readable sanity check: counts, spacing, monotonic timestamps."""
    beats: List[float] = result["beats"]
    downbeats: List[float] = result["downbeats"]
    tempo: float = result["tempo"]

    spacings = [beats[i + 1] - beats[i] for i in range(min(20, len(beats) - 1))]
    mean_spacing = sum(spacings) / len(spacings) if spacings else 0.0
    expected = 60.0 / tempo if tempo > 0 else 0.0
    monotonic = all(b > beats[i] for i, b in enumerate(beats[1:]))
    in_range = beats[-1] > 0

    print(f"tempo: {tempo} bpm")
    print(f"beats: {len(beats)}  downbeats: {len(downbeats)}")
    print(f"first beats:     {[round(b, 2) for b in beats[:10]]}")
    print(f"first downbeats: {[round(b, 2) for b in downbeats[:10]]}")
    print(f"mean early spacing: {mean_spacing:.4f}s (expected ~{expected:.4f}s)")
    print(f"monotonic: {monotonic}  last beat: {round(beats[-1], 2)}s")
    print(f"downbeat spacing: {round(downbeats[1] - downbeats[0], 4)}s "
          f"(expected ~{expected * 4:.4f}s)" if len(downbeats) > 1 else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract tempo, beats and downbeats from an audio file.")
    parser.add_argument("audio", type=str, help="path to the audio file")
    args = parser.parse_args()

    result = extract_beats(args.audio)
    _print_summary(result)
