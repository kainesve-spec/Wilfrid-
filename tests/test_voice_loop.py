"""Tests P1-B1 boucle vocale : raccords, échecs honnêtes, sans Android."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from core.voice.voice_loop import VoiceLoop, VoiceTurnReport, describe


class FakeResult:
    def __init__(self, kind="RESPONDED", text="Bien reçu."):
        self.kind = kind
        self.response = type("R", (), {"text": text,
                                       "kind": "CONTINUE"})()


class FakeRuntime:
    def __init__(self, kind="RESPONDED", text="Bien reçu."):
        self.kind = kind
        self.text = text
        self.texts = []
        self.running = False

    def run_turn(self, text, **_kw):
        self.texts.append(text)
        return True, FakeResult(self.kind, self.text)


def _pcm():
    return b"\x01\x00" * 3200


def _stt_ok(text="Bonjour", conf=0.9):
    def fake(_ref):
        return (text, conf)
    return fake


def _synth_played(played):
    def fake_synth(text):
        played.append(text)
        return b"WAV:" + text.encode("utf-8")[:16]
    def fake_play(audio):
        played.append(audio)
        return True, "joue"
    return fake_synth, fake_play


def test_a_micro_indisponible():
    calls = []

    def broken_capture():
        calls.append(1)
        raise OSError("micro HS")

    loop = VoiceLoop(FakeRuntime(), capture_fn=broken_capture,
                     stt_fn=_stt_ok())
    report = loop.turn_once()
    assert report.stage == "echec-capture"
    assert calls == [1]


def test_b_stt_indisponible():
    def broken(_ref):
        raise RuntimeError("moteur HS")

    loop = VoiceLoop(FakeRuntime(), capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=broken)
    report = loop.turn_once()
    assert report.stage == "echec-stt"


def test_c_texte_vide_sans_action():
    runtime = FakeRuntime()
    loop = VoiceLoop(runtime, capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok("   ", 0.9))
    report = loop.turn_once()
    assert report.stage == "silence"
    assert runtime.texts == []


def test_d_reponse_normale_synthetisee():
    runtime = FakeRuntime(text="Analyse terminée.")
    played = []
    synth, play = _synth_played(played)
    loop = VoiceLoop(runtime, capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok("Bonjour"), synth_fn=synth,
                     play_fn=play)
    report = loop.turn_once()
    assert report.stage == "termine"
    assert report.texte == "Bonjour"
    assert report.reponse == "Analyse terminée."
    assert played[0] == "Analyse terminée."


def test_e_tts_echoue():
    def broken(_text):
        raise RuntimeError("tts HS")

    loop = VoiceLoop(FakeRuntime(), capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok(), synth_fn=broken)
    report = loop.turn_once()
    assert report.stage == "echec-tts"


def test_f_lecture_echouee():
    played = []

    def fake_synth(text):
        return b"WAV"

    def fake_play(_audio):
        return False, "haut-parleur-absent"

    loop = VoiceLoop(FakeRuntime(), capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok(), synth_fn=fake_synth,
                     play_fn=fake_play)
    report = loop.turn_once()
    assert report.stage == "echec-lecture"
    assert report.tts == "ok"
    assert played == []


def test_g_approbation_respectee():
    runtime = FakeRuntime(kind="CONFIRM_CREATED",
                          text="Confirmation requise : test.")
    played = []
    synth, play = _synth_played(played)
    loop = VoiceLoop(runtime, capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok("oui"), synth_fn=synth, play_fn=play)
    report = loop.turn_once()
    assert report.core == "CONFIRM_CREATED"
    assert report.stage == "termine"
    assert played[0] == "Confirmation requise : test."


def test_h_refus_sans_execution():
    runtime = FakeRuntime(kind="RESPONDED", text="Je ne peux pas.")
    loop = VoiceLoop(runtime, capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=_stt_ok("supprime tout"))
    report = loop.turn_once()
    assert report.stage in ("termine", "echec-tts", "echec-lecture")
    assert runtime.texts == ["supprime tout"]


def test_i_arret_pendant_attente():
    loop = VoiceLoop(FakeRuntime(), max_turns=0)
    out = loop.stop()
    assert out["etat"] == "STOPPED"
    done = loop.run()
    assert done["etat"] == "STOPPED" and done["tours"] == 0


def test_j_arret_pendant_traitement():
    loop = VoiceLoop(FakeRuntime(), capture_fn=lambda: (_pcm(), 16000),
                     max_turns=5)

    def stopper(_ref):
        loop.stop()
        return ("Bonjour", 0.9)

    loop._stt_fn = stopper
    report = loop.turn_once()
    assert report.stage == "termine"
    done = loop.run()
    assert done["etat"] == "STOPPED"
    assert loop._wake is None


def test_k_plusieurs_tours_sans_duplication():
    runtime = FakeRuntime()
    played = []
    synth, play = _synth_played(played)
    texts = ["un", "deux", "trois"]

    def staged(_ref):
        return (texts.pop(0), 0.9)

    loop = VoiceLoop(runtime, capture_fn=lambda: (_pcm(), 16000),
                     stt_fn=staged, synth_fn=synth, play_fn=play,
                     max_turns=3)
    done = loop.run()
    assert done == {"tours": 3, "etat": "STOPPED",
                    "raison": "arret-explicite"}
    assert runtime.texts == ["un", "deux", "trois"]
    assert played[0::2] == ["Bien reçu.", "Bien reçu.", "Bien reçu."]
    assert len(loop.reports) == 3


def test_wake_silence_honnete():
    from core.audio.capture import ArraySource
    from core.wake.runtime import WakeRuntime
    silence = np.zeros(1600 * 30, dtype=np.int16)

    def factory():
        return WakeRuntime(source=ArraySource(silence, blocksize=1600))

    loop = VoiceLoop(FakeRuntime(), wake_factory=factory,
                     wake_timeout_s=3.0)
    heard, why = loop.listen_once()
    assert heard is False
    assert why == "silence-delai-depasse"


def test_wake_invalide():
    loop = VoiceLoop(FakeRuntime(), wake_factory=lambda: "pas-un-wake")
    heard, why = loop.listen_once()
    assert heard is False and why == "wake-invalide"


def test_l_sans_android_ni_elevenlabs():
    src = Path("core/voice/voice_loop.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "termux-tts-speak" not in lowered
    assert "texttospeech" not in lowered
    assert "elevenlabs" not in lowered
    assert "WILFRID_ALLOW_ANDROID_TTS" not in src
    assert "stt_fn_for" in src
    assert "speak_validated" in src
    assert "play_wav" in src
    assert "sounddevice_pcm_capture" in src
    info = describe()
    assert info["network"] is False and info["authority"] is False
    assert "whisper-local" in info["defauts"]
    assert "pierre-locale" in info["defauts"]
