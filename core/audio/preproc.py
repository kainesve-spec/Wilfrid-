"""Wilfrid — preprocessing streaming (P3.2). Mêmes formules que le
harnais P1 (`tools/score_wavs.py`, lui-même fidèle à heed/audio.py),
avec conservation d'état pour le streaming :
- StreamingFilter : HPF Butterworth 8/100 Hz + notch 50/60 Hz Q=30,
  causal sosfilt, état conservé entre blocs (bit-identique au continu).
- peak_normalize : -3 dBFS par fenêtre évaluée.
- compute_mel : STFT 512/400/160, Hann périodique, center reflect,
  mel HTK 40 (0-8000), log clamp 1e-9, CMN.
- energy_gate_open : RMS -55 dBFS + fraction bande-voix 100-7000 Hz.
- RingBuffer : circulaire préalloué 16000, sans allocation par cycle.

AUCUN trim, AUCUN center : réservés au pipeline offline P1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from scipy import signal as _ssig

SAMPLE_RATE = 16000
WINDOW_SAMPLES = 16000
N_FFT, WIN_LENGTH, HOP_length, N_MELS = 512, 400, 160, 40
HPF_CUTOFF, HPF_ORDER = 100.0, 8
NOTCH_FREQS, NOTCH_Q = (50.0, 60.0), 30.0
PEAK_DBFS = -3.0
MEL_FMIN, MEL_FMAX = 0.0, 8000.0
GATE_DBFS = -55.0
GATE_BAND_LO, GATE_BAND_HI, GATE_BAND_MIN = 100.0, 7000.0, 0.15


class StreamingFilter:
    """HPF + notches causaux à état (cf. heed StreamingHighpass)."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self._stages: List = []
        sos = _ssig.butter(HPF_ORDER, HPF_CUTOFF, btype="highpass",
                           fs=sample_rate, output="sos")
        self._stages.append([sos, None])
        for freq in NOTCH_FREQS:
            b, a = _ssig.iirnotch(freq, NOTCH_Q, fs=sample_rate)
            self._stages.append([_ssig.tf2sos(b, a), None])

    def reset(self) -> None:
        for i, (sos, _zi) in enumerate(self._stages):
            self._stages[i][1] = None

    def __call__(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float64).flatten()
        if x.size == 0:
            return np.ascontiguousarray(
                np.empty(0, dtype=np.float32))
        for i, (sos, zi) in enumerate(self._stages):
            if zi is None:
                zi = _ssig.sosfilt_zi(sos) * x[0]
            x, zi = _ssig.sosfilt(sos, x, zi=zi)
            self._stages[i][1] = zi
        return np.ascontiguousarray(x.astype(np.float32))


def peak_normalize(x: np.ndarray, target_dbfs: float = PEAK_DBFS) -> np.ndarray:
    peak = float(np.abs(x).max(initial=0.0)) if x.size else 0.0
    if peak < 1e-6:
        return np.asarray(x, dtype=np.float32)
    return (np.asarray(x, dtype=np.float32)
            * (10 ** (target_dbfs / 20.0) / max(peak, 1e-9))).astype(np.float32)


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _mel_filterbank(n_mels: int = N_MELS, n_fft: int = N_FFT,
                    sample_rate: int = SAMPLE_RATE,
                    fmin: float = MEL_FMIN, fmax: float = MEL_FMAX) -> np.ndarray:
    mel_pts = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz_pts = np.array([_mel_to_hz(m) for m in mel_pts])
    freqs = np.linspace(0.0, sample_rate / 2, n_fft // 2 + 1)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(n_mels):
        left, center, right = hz_pts[m], hz_pts[m + 1], hz_pts[m + 2]
        rising = (freqs - left) / (center - left + 1e-9)
        falling = (right - freqs) / (right - center + 1e-9)
        fb[m] = np.clip(np.minimum(rising, falling), 0.0, None)
    return fb


_MEL_FB = _mel_filterbank()
_HANN = (0.5 - 0.5 * np.cos(
    2.0 * np.pi * np.arange(WIN_LENGTH) / WIN_LENGTH)).astype(np.float32)


def compute_mel(x_16000: np.ndarray) -> Tuple[np.ndarray, int]:
    """Mel 40x101 + CMN d'une fenêtre complète de 16000 samples."""
    if x_16000.size != WINDOW_SAMPLES:
        raise ValueError(f"fenêtre {x_16000.size} != {WINDOW_SAMPLES}")
    y = np.pad(x_16000.astype(np.float64), N_FFT // 2, mode="reflect")
    n_frames = 1 + (y.size - WIN_LENGTH) // HOP_length
    spec = np.empty((N_FFT // 2 + 1, n_frames))
    for t in range(n_frames):
        frame = y[t * HOP_length:t * HOP_length + WIN_LENGTH] * _HANN
        spec[:, t] = np.abs(np.fft.rfft(frame, n=N_FFT)) ** 2
    mel = _MEL_FB @ spec
    out = np.log(np.clip(mel, 1e-9, None))
    out = out - out.mean(axis=-1, keepdims=True)
    return out.astype(np.float32), n_frames


def energy_gate_open(x_16000: np.ndarray,
                     threshold_dbfs: float = GATE_DBFS,
                     band_lo: float = GATE_BAND_LO,
                     band_hi: float = GATE_BAND_HI,
                     band_min: float = GATE_BAND_MIN,
                     sample_rate: int = SAMPLE_RATE) -> Tuple[bool, dict]:
    """Gate heed/gate.py transposé : RMS puis fraction bande-voix."""
    n = int(np.asarray(x_16000).size)
    if n < 64:
        return False, {"reason": "too short", "rms_dbfs": -120.0,
                       "band_frac": 0.0}
    flat = np.asarray(x_16000, dtype=np.float64).flatten()
    rms = float(np.sqrt((flat ** 2).mean()))
    rms_dbfs = 20.0 * math.log10(max(rms, 1e-9))
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)
    mag = np.abs(np.fft.rfft(flat * window)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    total = max(float(mag.sum()), 1e-12)
    band_frac = float(mag[(freqs >= band_lo) & (freqs <= band_hi)].sum() / total)
    diag = {"rms": rms, "rms_dbfs": rms_dbfs, "band_frac": band_frac}
    if rms < 10 ** (threshold_dbfs / 20.0):
        diag["reason"] = "below energy"
        return False, diag
    if band_frac < band_min:
        diag["reason"] = "out of voice band"
        return False, diag
    diag["reason"] = "pass"
    return True, diag


class RingBuffer:
    """Circulaire préalloué (zéro allocation par cycle en régime établi)."""

    def __init__(self, size: int = WINDOW_SAMPLES):
        self.size = size
        self.buf = np.zeros(size, dtype=np.float32)
        self.filled = 0

    def reset(self) -> None:
        self.buf[:] = 0.0
        self.filled = 0

    def push(self, block: np.ndarray) -> None:
        block = np.asarray(block, dtype=np.float32).flatten()
        n = block.size
        if n >= self.size:
            self.buf[:] = block[-self.size:]
            self.filled = self.size
            return
        self.buf[:-n] = self.buf[n:]
        self.buf[-n:] = block
        self.filled = min(self.size, self.filled + n)

    def full(self) -> bool:
        return self.filled >= self.size

    def window(self) -> np.ndarray:
        return self.buf.copy()
