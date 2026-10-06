"""Tests P3.2 — preprocessing streaming (données synthétiques + WAV, lecture seule)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import signal as ssig

from core.audio.preproc import (
    RingBuffer,
    StreamingFilter,
    compute_mel,
    energy_gate_open,
    peak_normalize,
)


def _sine_440(n=16000, amp=0.5):
    t = np.arange(n) / 16000.0
    return (amp * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def test_mel_shape():
    """C. preprocessing shape 40x101."""
    mel, n_frames = compute_mel(_sine_440())
    assert mel.shape == (40, 101)
    assert n_frames == 101
    assert np.all(np.isfinite(mel))


def test_mel_deterministic():
    """D. preprocessing déterministe."""
    x = _sine_440()
    m1, _ = compute_mel(x)
    m2, _ = compute_mel(x)
    assert np.array_equal(m1, m2)


def test_mel_rejects_bad_window():
    mel_bad = None
    try:
        compute_mel(np.zeros(100, dtype=np.float32))
    except ValueError:
        mel_bad = True
    assert mel_bad is True


def test_chunked_equals_continuous():
    """F. filtrage chunk-à-chunk identique au continu (HPF + 2 notch)."""
    rng = np.random.default_rng(7)
    x = (rng.standard_normal(16000) * 0.3).astype(np.float64)
    sos = ssig.butter(8, 100.0, btype="highpass", fs=16000, output="sos")
    stages = [sos]
    for freq in (50.0, 60.0):
        b, a = ssig.iirnotch(freq, 30.0, fs=16000)
        stages.append(ssig.tf2sos(b, a))

    def continuous(sig):
        y = sig
        for stage in stages:
            zi = ssig.sosfilt_zi(stage)
            y, _ = ssig.sosfilt(stage, y, zi=zi * y[0])
        return y

    ref = continuous(x)
    filt = StreamingFilter()
    parts = [filt(x[i:i + 1600]) for i in range(0, len(x), 1600)]
    got = np.concatenate([np.asarray(p, dtype=np.float64) for p in parts])
    err = np.abs(ref - got)
    # Sortie bloc float32 par conception (mémoire) : tolérance 1e-6.
    # Le diagnostic P3 a prouvé 0.0 exact en float64-vs-float64.
    assert err.max() < 1e-6
    # reset : même résultat après réinitialisation
    filt.reset()
    parts2 = [filt(x[i:i + 1600]) for i in range(0, len(x), 1600)]
    got2 = np.concatenate([np.asarray(p, dtype=np.float64) for p in parts2])
    assert np.array_equal(got, got2)


def test_energy_gate():
    """E. energy gate : silence fermé, voix ouverte."""
    shut, diag_shut = energy_gate_open(np.zeros(16000, dtype=np.float32))
    assert shut is False
    assert diag_shut["reason"] == "below energy"
    open_, diag_open = energy_gate_open(_sine_440())
    assert open_ is True
    assert diag_open["reason"] == "pass"


def test_ring_buffer():
    """O. buffer glissant : plein après 16000, fenêtre = derniers samples."""
    ring = RingBuffer()
    assert not ring.full()
    for i in range(10):
        ring.push(np.full(1600, float(i), dtype=np.float32))
    assert ring.full()
    w = ring.window()
    assert w.shape == (16000,)
    assert float(w[0]) == 0.0 and float(w[-1]) == 9.0
    ring.push(np.full(1600, 10.0, dtype=np.float32))
    w2 = ring.window()
    assert float(w2[0]) == 1.0 and float(w2[-1]) == 10.0
    ring.reset()
    assert not ring.full()


def test_peak_normalize():
    x = (np.arange(16000, dtype=np.float32) - 8000.0) / 8000.0
    y = peak_normalize(x)
    assert abs(float(np.abs(y).max()) - 10 ** (-3.0 / 20.0)) < 1e-6
    z = peak_normalize(np.zeros(100, dtype=np.float32))
    assert np.all(z == 0.0)
