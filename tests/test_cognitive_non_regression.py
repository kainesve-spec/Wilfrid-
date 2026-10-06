"""Tests P5 — non-régression P1/P2/P3 (lecture seule, aucune écriture)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

P1_PINS = {
    "models/wake.onnx":
        "87eead450ef6c2964229f40c936dc03d205dd0bb3d63c33806e8f5a68fa6d333",
    "models/wake.json":
        "c8c62f8b2358e4bdb74149eebfd992f4dbc6d15b13527c24fa42b7169dc09e06",
    "tools/score_wavs.py":
        "269ba8d1adf1e051e39be1f00476ef2e5860f1cef63ace26d6b19394dcd64dd9",
    "tests/test_wake_harness.py":
        "7a09c6a27cfc35ab0bd4ee33a19366c6068f9cbebf65ad56bc6f0dbace6ea272",
}


def test_p1_pins():
    """Artefacts P1 intacts (références gelées)."""
    for rel, digest in P1_PINS.items():
        assert hashlib.sha256(
            (PROJECT_ROOT / rel).read_bytes()).hexdigest() == digest, rel


def test_threshold_unchanged():
    meta = json.loads((PROJECT_ROOT / "models" / "wake.json").read_text(
        encoding="utf-8"))
    assert float(meta["threshold"]) == 0.665


def test_p2_intact():
    """P2 importable et fonctionnel (aucune modification P5)."""
    import jarvis  # noqa: F401
    import core.audio  # noqa: F401
    import core.voice  # noqa: F401
    import core.actions  # noqa: F401

    assert jarvis.block_samples() == 1764


def test_p3_p4_intact():
    """P3/P4 importables, contrats inchangés."""
    import core.audio.capture  # noqa: F401
    import core.audio.preproc  # noqa: F401
    import core.session.manager  # noqa: F401
    import core.wake.detector  # noqa: F401
    from core.wake.events import WakeDetected  # noqa: F401

    assert WakeDetected(timestamp_monotonic=0.0, probability=0.9).phrase == \
        "Wilfrid"


def test_no_memory_no_stt():
    """Aucune mémoire/STT introduite par P5 (ni ailleurs de neuf)."""
    assert not (PROJECT_ROOT / "memory").exists()
    assert not list(PROJECT_ROOT.glob("memory.db"))
    assert not list((PROJECT_ROOT / "core").glob("stt*"))
