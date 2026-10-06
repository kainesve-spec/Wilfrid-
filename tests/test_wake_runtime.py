"""Tests P3.4 — runtime (sources simulées, WAV existants non modifiés)."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from core.audio.capture import ArraySource
from core.wake.events import WakeDetected
from core.wake.runtime import WakeRuntime, WakeRuntimeError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL = PROJECT_ROOT / "models" / "wake.onnx"
META = PROJECT_ROOT / "models" / "wake.json"


def _wav_samples(name: str) -> np.ndarray:
    import struct

    raw = (PROJECT_ROOT / name).read_bytes()
    return np.frombuffer(raw[44:], dtype=np.int16)


def _runtime(samples: np.ndarray, **kw):
    events = []
    rt = WakeRuntime(model_path=MODEL, meta_path=META,
                     source=ArraySource(samples), on_wake=events.append, **kw)
    return rt, events


def test_model_validation():
    """B. validation modèle : nom/forme/dtype vérifiés au démarrage."""
    rt, _ = _runtime(np.zeros(1600, dtype=np.int16))
    rt._load_model()
    assert rt._session is not None


def test_missing_model_and_meta():
    """N. erreurs modèle/config explicites."""
    with pytest.raises(WakeRuntimeError):
        WakeRuntime(model_path="no_model.onnx", meta_path=META,
                    source=ArraySource(np.zeros(1600, dtype=np.int16)))._load_model()
    with pytest.raises(WakeRuntimeError):
        WakeRuntime(model_path=MODEL, meta_path="no_meta.json",
                    source=ArraySource(np.zeros(1600, dtype=np.int16)))
    from core.wake.runtime import MODEL_PATH_DEFAULT
    assert MODEL_PATH_DEFAULT == "models/wake.onnx"


def test_simulated_run_metrics():
    """Intégration simulée : métriques et états, aucune action."""
    rt, events = _runtime(_wav_samples("wake_test_1s.wav"))
    snap = rt.run()
    assert snap["frames_received"] == 10
    # run() se termine arrêté ; l'état pendant l'écoute est LISTENING+.
    assert snap["current_state"] == "STOPPED"
    assert snap["threshold"] == pytest.approx(0.665)
    assert isinstance(events, list)
    for event in events:
        assert isinstance(event, WakeDetected)
        assert event.phrase == "Wilfrid"


def test_silence_scores_nothing():
    """Silence : gate fermé, zéro trigger, zéro erreur."""
    rt, events = _runtime(np.zeros(16000, dtype=np.int16))
    snap = rt.run()
    assert snap["gate_closed"] >= 1
    assert snap["triggers"] == 0
    assert events == []
    assert snap["audio_errors"] == 0


def test_stop_timing():
    """M. stop() < 1 seconde sur runtime actif."""
    rt, _ = _runtime(_wav_samples("wake_test_1s.wav"))
    rt.start()
    time.sleep(0.3)
    elapsed = rt.stop()
    assert elapsed < 1.0
    assert rt.detector.state.value == "STOPPED"


def test_determinism():
    """Deux passes simulées identiques (mêmes triggers)."""
    def run_once():
        rt, events = _runtime(_wav_samples("wake_test_1s.wav"))
        rt.run()
        return [(e.timestamp_monotonic is not None, round(e.probability, 9))
                for e in events]
    assert run_once() == run_once()
