"""Tests routeur hybride : sélection, fallback, config, preuve offline."""

from __future__ import annotations

import ast
import wave
from pathlib import Path

from core.voice import voice_router
from core.voice.voice_router import (
    VoiceConfig,
    elevenlabs_available,
    load_config,
    save_config,
    speak_validated,
)


def _connected_audio(text):
    return b"CONNECTED:" + text.encode("utf-8")[:32]


def test_a_connecte_injecte():
    status, audio, report = speak_validated(
        "Bonjour.", convert_fn=_connected_audio)
    assert status == "OK"
    assert audio.startswith(b"CONNECTED:")
    assert report.provider == "elevenlabs"
    assert report.offline is False and report.fallback is False


def test_b_offline_force_local():
    status, audio, report = speak_validated("Bonjour.", offline_forced=True)
    assert status == "OK"
    assert audio[:4] == b"RIFF"
    assert report.provider == "local"
    assert report.offline is True


def test_c_fallback_local():
    def broken(text):
        raise RuntimeError("reseau HS")
    status, audio, report = speak_validated(
        "Bonjour.", convert_fn=broken)
    assert status == "OK"
    assert audio[:4] == b"RIFF"
    assert report.provider == "local"
    assert report.fallback is True


def test_c_bloque_sans_repli():
    def broken(text):
        raise RuntimeError("reseau HS")
    cfg = VoiceConfig(mode="connected")
    status, audio, report = speak_validated(
        "Bonjour.", config=cfg, convert_fn=broken)
    assert status == "FAILED"
    assert audio == b""
    assert report.fallback is False


def test_d_nombres_prepares():
    status, audio, report = speak_validated(
        "Le montant est de 100 USDT.", convert_fn=_connected_audio)
    assert status == "OK"
    assert report.spoken_text == "Le montant est de cent U S D T."


def test_e_acronymes():
    _, _, report = speak_validated("TAIOS.", convert_fn=_connected_audio)
    assert report.spoken_text == "T A I O S."


def test_f_dictionnaire():
    _, _, report = speak_validated(
        "Ouvrir TAIOS.", convert_fn=_connected_audio,
        dictionary={"TAIOS": "tayos"})
    assert report.spoken_text == "Ouvrir tayos."


def test_g_phrase_longue():
    text = ("Bien reçu. J'ai terminé l'analyse du document et je reste "
            "disponible pour la suite.")
    status, audio, report = speak_validated(text, offline_forced=True)
    assert status == "OK" and len(audio) > 10000


def test_h_reponse_courte():
    status, audio, report = speak_validated("Bien reçu.",
                                            offline_forced=True)
    assert status == "OK" and len(audio) > 1000


def test_i_config_persiste(tmp_path):
    target = tmp_path / "voice.json"
    cfg = VoiceConfig(mode="local", offline_voice="upmc-pierre",
                      offline_sid=1, dictionary={"TAIOS": "tayos"})
    ok, _ = save_config(cfg, target)
    assert ok is True
    back = load_config(target)
    assert back.mode == "local"
    assert back.offline_voice == "upmc-pierre"
    assert back.dictionary == {"TAIOS": "tayos"}
    assert back.connected_voice_id is None
    assert load_config(tmp_path / "absent.json").mode == "auto"
    assert load_config(tmp_path / "absent.json").offline_voice == \
        "upmc-pierre"


def test_j_preuve_offline_sans_reseau():
    src = Path("core/voice/voice_router.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"socket", "urllib", "http", "requests"}), mods
    tts = Path("core/voice/tts_local.py").read_text(encoding="utf-8")
    assert "urllib" not in tts and "requests" not in tts
    assert "socket" not in tts
    status, audio, report = speak_validated("Bonjour.", offline_forced=True)
    assert status == "OK" and report.offline is True


def test_r0_routeur_local():
    status, audio, report = speak_validated(
        "Bien reçu.", offline_forced=True)
    assert status == "OK"
    with wave.open(__import__("io").BytesIO(audio), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getnframes() > 1000


def test_r1_confirmation_vocalisee():
    text = "Confirmation requise : P7.JAIL_READ sur notes."
    status, audio, report = speak_validated(text, offline_forced=True)
    assert status == "OK"
    assert "Confirmation requise" in report.spoken_text


def test_texte_vide_et_borne():
    status, audio, report = speak_validated("   ", offline_forced=True)
    assert status == "SKIPPED" and audio == b""
    status, audio, report = speak_validated("x" * 5000,
                                            offline_forced=True)
    assert status == "FAILED"


def test_elevenlabs_sans_presomption():
    available, reason = elevenlabs_available()
    assert isinstance(available, bool) and isinstance(reason, str)
    assert voice_router.describe()["official_offline_voice"] == \
        "upmc-pierre"
    assert voice_router.describe()["authority"] is False


def test_routeur_sans_autorite():
    src = Path("core/voice/voice_router.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    called: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    assert not (called & {"invoke", "approve_confirmation",
                          "deny_confirmation", "revoke", "suspend",
                          "PermissionRegistry", "ApprovalGate",
                          "MandateRegistry", "submit_turn",
                          "resolve_confirmation"}), called
    assert "shell" not in src
    assert "sk-" not in src and "sk_live" not in src
    assert "ELEVENLABS_API_KEY" in src
    assert "print(" not in src
