"""Tests P3.1 — détecteur à états (synthétique, aucun audio, aucun modèle)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.wake.detector import DetectorState, WakeDetector, WakeRuntimeConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAKE_JSON = PROJECT_ROOT / "models" / "wake.json"


def _detector(**kw):
    cfg_kwargs = dict(threshold=0.665, consecutive_frames=2,
                      refractory_seconds=0.7, ema_alpha=0.5,
                      energy_dbfs=-55.0, voice_band_min=0.15,
                      band_lo_hz=100.0, band_hi_hz=7000.0,
                      sample_rate=16000, phrase="Wilfrid")
    cfg_kwargs.update(kw)
    det = WakeDetector(WakeRuntimeConfig(**cfg_kwargs))
    det.start()
    return det


def test_config_load():
    """A. chargement configuration depuis wake.json (seuil non codé en dur)."""
    cfg = WakeRuntimeConfig.from_wake_json(WAKE_JSON)
    assert cfg.threshold == pytest.approx(0.665)
    assert cfg.consecutive_frames == 2
    assert cfg.refractory_seconds == pytest.approx(0.7)
    assert cfg.ema_alpha == pytest.approx(0.5)
    assert cfg.energy_dbfs == pytest.approx(-55.0)
    assert cfg.voice_band_min == pytest.approx(0.15)
    assert (cfg.band_lo_hz, cfg.band_hi_hz) == (100.0, 7000.0)
    assert cfg.sample_rate == 16000


def test_single_frame_above_no_trigger():
    """G. une frame > threshold → aucun trigger."""
    det = _detector()
    assert det.step(0.10, True, now=0.0) is None
    assert det.step(0.80, True, now=0.1) is None
    assert det.step(0.10, True, now=0.2) is None
    assert det.metrics["triggers"] == 0


def test_two_consecutive_trigger():
    """H. deux frames consécutives > threshold → trigger."""
    det = _detector()
    det.step(0.10, True, now=0.0)
    assert det.step(0.80, True, now=0.1) is None
    event = det.step(0.85, True, now=0.2)
    assert event is not None
    assert event.probability == pytest.approx(0.85)
    assert event.phrase == "Wilfrid"
    assert det.metrics["triggers"] == 1


def test_separated_frames_no_trigger():
    """I. frames séparées par une frame < threshold → aucun trigger."""
    det = _detector()
    seq = [0.80, 0.10, 0.80, 0.10, 0.80, 0.10]
    events = [det.step(p, True, now=i * 0.1) for i, p in enumerate(seq)]
    assert all(e is None for e in events)


def test_refractory():
    """J. deux triggers < 0.7 s → un seul ; > 0.7 s → deux."""
    det = _detector()
    first = [det.step(p, True, now=i * 0.1) for i, p in enumerate([0.8, 0.85])]
    assert first[1] is not None  # t=0.1
    second = [det.step(p, True, now=0.2 + i * 0.1) for i, p in enumerate([0.8, 0.85])]
    assert all(e is None for e in second)  # t=0.2/0.3 : réfractaire
    third = [det.step(p, True, now=1.0 + i * 0.1) for i, p in enumerate([0.8, 0.85])]
    assert third[1] is not None  # t=1.1 : hors réfractaire
    assert det.metrics["triggers"] == 2


def test_gate_reset():
    """K. fermeture du gate entre deux candidates → aucun trigger."""
    det = _detector()
    assert det.step(0.80, True, now=0.0) is None
    assert det.step(0.10, False, now=0.1) is None  # gate fermé : reset
    assert det.step(0.85, True, now=0.2) is None
    assert det.metrics["triggers"] == 0
    assert det.metrics["gate_closed"] == 1


def test_event_and_ema_display_only():
    """L/F. événement minimal ; EMA n'influence pas la porte."""
    seen = []
    det = _detector()
    det.on_wake = seen.append
    det.step(0.80, True, now=0.0)
    event = det.step(0.85, True, now=0.1)
    assert seen == [event]
    assert event.timestamp_monotonic == pytest.approx(0.1)
    assert event.frame_index == -1
    # EMA basse (démarrage) n'empêche pas le trigger : porte = prob brute.
    assert det.ema < 0.665
    assert det.metrics["triggers"] == 1


def test_stop():
    """M. stop → STOPPED, plus aucun trigger."""
    det = _detector()
    det.stop()
    assert det.state == DetectorState.STOPPED
    assert det.step(0.99, True, now=0.0) is None
    assert det.step(0.99, True, now=0.1) is None
    assert det.metrics["triggers"] == 0


def test_metrics():
    det = _detector()
    det.step(0.10, True, now=0.0)
    det.step(0.80, True, now=0.1)
    det.step(0.85, True, now=0.2)
    assert det.metrics["windows_scored"] == 3
    assert det.metrics["gate_open"] == 3
    assert det.metrics["scores_above_threshold"] == 2
    assert det.metrics["triggers"] == 1
    assert det.last_probability == pytest.approx(0.85)
