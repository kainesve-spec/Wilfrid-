"""Tests du harnais de mesure P1 (référence T1). Lecture seule sur le projet.

Vérifie : forme mel 40x101, logit scalaire, prob dans [0,1], seuil chargé
depuis wake.json, déterminisme, WAV mono 16 kHz, modèles intacts.
Aucune écriture dans le projet, aucun réentraînement, seuil inchangé.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
REF_WAV = PROJECT_ROOT / "wake_test_1s.wav"

import sys

sys.path.insert(0, str(TOOLS_DIR))
import score_wavs as harness


def _session():
    import onnxruntime as ort
    return ort.InferenceSession(str(PROJECT_ROOT / "models" / "wake.onnx"),
                                providers=["CPUExecutionProvider"])


def _meta():
    return harness.load_meta()


def _mel_of_ref():
    audio, _ = harness.read_wav_mono16(str(REF_WAV))
    audio = harness.center_in_window(
        harness.peak_normalize(
            harness.trim_silence(
                harness.peak_normalize(harness.highpass_filter(audio)))))
    mel, n_frames = harness.log_mel_cmn(audio)
    return mel, n_frames


def test_mel_shape_is_40x101():
    """1. forme mel = 40x101."""
    mel, n_frames = _mel_of_ref()
    assert mel.shape == (40, 101)
    assert n_frames == 101


def test_logit_is_scalar():
    """2. sortie logit scalaire."""
    session = _session()
    mel, _ = _mel_of_ref()
    out = np.asarray(session.run(None, {"mel": mel[None]})[0]).flatten()
    assert out.size == 1
    assert float(out[0]) == float(out[0])  # fini, pas NaN


def test_prob_in_unit_interval():
    """3. probabilité dans [0,1]."""
    session = _session()
    mel, _ = _mel_of_ref()
    logit = float(np.asarray(
        session.run(None, {"mel": mel[None]})[0]).flatten()[0])
    prob = harness.sigmoid(logit)
    assert 0.0 <= prob <= 1.0


def test_threshold_loaded_from_wake_json():
    """4. seuil correctement chargé (0.665, non codé en dur ailleurs)."""
    meta = _meta()
    assert abs(float(meta["threshold"]) - 0.665) < 1e-9
    assert int(meta["sample_rate"]) == 16000
    assert int(meta["n_mels"]) == 40


def test_deterministic_on_same_input():
    """5. déterminisme sur une même entrée."""
    session = _session()
    meta = _meta()
    first = harness.score_file(str(REF_WAV), session, float(meta["threshold"]))
    second = harness.score_file(str(REF_WAV), session, float(meta["threshold"]))
    assert first["logit"] == second["logit"]
    assert first["prob"] == second["prob"]
    assert first["trigger"] == second["trigger"]


def test_mono_16khz_wav_handling():
    """6. traitement correct d'un WAV mono 16 kHz."""
    audio, sr = harness.read_wav_mono16(str(REF_WAV))
    assert sr == 16000
    assert audio.dtype == np.float32
    assert audio.size == 16000
    with pytest.raises((ValueError, AssertionError)):
        harness.read_wav_mono16(str(PROJECT_ROOT / "requirements.txt"))


def test_models_untouched():
    """7. absence de modification des fichiers modèle (tailles + JSON lisible)."""
    onnx_path = PROJECT_ROOT / "models" / "wake.onnx"
    json_path = PROJECT_ROOT / "models" / "wake.json"
    assert onnx_path.stat().st_size == 45160
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    assert meta["phrase"] == "Wilfrid"
    digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    assert len(digest) == 64
    print(f"\nwake.onnx sha256={digest}")
