"""Energy analysis: audio file -> energy_curve + bass_hits.

energy_curve: normalized RMS envelope sampled ~10x per second, values 0..1.
  This drives the arena pulse and the general "how alive is the song now".
bass_hits: sharp onset peaks in the low-frequency band (< 150 Hz). These are
  the punchy kick/bass moments the simulation uses for big impact events.
"""

import argparse
from pathlib import Path
from typing import Dict, List, Union

import librosa
import numpy as np
from scipy import signal

DEFAULT_SR = 22050
ENERGY_HOP_S = 0.1      # energy curve sample spacing (s)
BASS_CUTOFF = 150.0     # Hz - top of the "bass/kick" band
BASS_HOP_S = 0.02       # hop for bass onset detection (s)
BASS_MIN_GAP_S = 0.25   # ignore new bass hits closer than this to a previous one (s)
BEAT_TOL_S = 0.12       # bass hit counts as "on the beat" within this tolerance (s)


def extract_energy(audio_path: Union[str, Path], sr: int = DEFAULT_SR) -> Dict[str, object]:
    """Return {'energy_curve': [[t, e], ...], 'bass_hits': [t, ...]}.

    Values are rounded so the result is directly JSON-serializable for timeline.json.
    """
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True)

    # --- RMS energy envelope, normalized to 0..1 by its own peak ---
    hop_energy = max(1, int(sr * ENERGY_HOP_S))
    rms = librosa.feature.rms(y=y, hop_length=hop_energy)[0]
    peak = float(rms.max())
    normalized = (rms / peak) if peak > 0 else rms
    times_e = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_energy)
    energy_curve = [
        [round(float(t), 3), round(float(e), 4)]
        for t, e in zip(times_e, normalized)
    ]

    # --- bass hits: onset peaks in the low-pass filtered band ---
    hop_bass = max(1, int(sr * BASS_HOP_S))
    b, a = signal.butter(4, BASS_CUTOFF / (sr / 2.0), btype="low")
    y_bass = signal.filtfilt(b, a, y)
    onset_bass = librosa.onset.onset_strength(y=y_bass, sr=sr, hop_length=hop_bass)
    wait = max(1, int(BASS_MIN_GAP_S / BASS_HOP_S))
    peaks = librosa.util.peak_pick(
        onset_bass, pre_max=5, post_max=5, pre_avg=5, post_avg=30,
        delta=0.25, wait=wait,
    )
    bass_hits = [
        round(float(t), 3)
        for t in librosa.frames_to_time(peaks, sr=sr, hop_length=hop_bass)
    ]

    return {
        "energy_curve": energy_curve,
        "bass_hits": bass_hits,
    }


def _print_summary(result: Dict[str, object], beats: List[float]) -> None:
    """Human-readable sanity check for the analysis."""
    curve: List[List[float]] = result["energy_curve"]
    hits: List[float] = result["bass_hits"]
    energies = [e for _, e in curve]

    print(f"energy samples: {len(curve)}  (expect ~duration x 10 = ~{len(curve) // 10 * 10})")
    print(f"energy range: {min(energies):.3f} .. {max(energies):.3f}")
    print(f"bass hits: {len(hits)}")
    print(f"first bass hits: {[round(h, 2) for h in hits[:12]]}")
    print(f"last bass hit: {round(hits[-1], 2)}s" if hits else "no bass hits")

    # How many bass hits land close to a detected beat? (EDM kicks should align.)
    if beats and hits:
        near = sum(
            1 for h in hits
            if any(abs(b - h) < BEAT_TOL_S for b in beats)
        )
        print(f"bass hits within {BEAT_TOL_S}s of a beat: {near}/{len(hits)} "
              f"({100.0 * near / len(hits):.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract energy curve and bass hits from an audio file.")
    parser.add_argument("audio", type=str, help="path to the audio file")
    args = parser.parse_args()

    # Reuse the beat extractor to validate that bass hits sit on the beat grid.
    from beat_detect import extract_beats

    result = extract_energy(args.audio)
    beats = extract_beats(args.audio)["beats"]
    _print_summary(result, beats)
