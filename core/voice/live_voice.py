"""Wilfrid — pont voix → boucle vivante (interface, sans autorité).

Enchaîne : audio → STT injecté → `SpeechResult` → `LiveSession.submit_turn`
(même Core que le texte) → réponse validée → TTS injecté → audio. Aucun
moteur réel câblé : sans `stt_fn`, STT FAILED honnête ; sans `synth_fn`,
TTS SKIPPED honnête. La voix ne décide ni n'autorise rien : même pipeline,
mêmes garde-fous (clarification, confirmation, mandats, révocation).
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from core.loop.live import LiveSession, open_session, resolve_live, submit_turn
from core.loop.loop import LoopResult
from core.p7.approval_gate import ApprovalGate
from core.voice.interaction import (
    InterfaceState,
    SpeechOutput,
    SpeechResult,
    speak,
    transcribe,
)


def _announce(result: Any) -> str:
    """Annonce vocale honnête : issue vérifiée uniquement, jamais le contenu."""
    if result is None:
        return ""
    verified = getattr(result, "verification", "") == "VERIFIED_SUCCESS"
    if not verified:
        return ""
    if getattr(result, "kind", "") in ("EXECUTED", "CONFIRM_RESOLVED"):
        return "Action exécutée et vérifiée."
    return ""


def voice_turn(live: Any, gate: Any, audio_ref: Any, stt_fn: Any = None, *,
               now: Any, synth_fn: Any = None, play_fn: Any = None,
               search_fn: Any = None, memory: Any = None,
               memorize: bool = False, router_fn: Any = None,
               mandates: Any = None, journal: Any = None,
               payload: Any = None, catalog: Any = None,
               skill_id: str = "wilfrid-core",
               skill_version: str = "1.0",
               expires_at: Any = None,
               session_id: Any = None) -> Tuple[Any, LoopResult, SpeechOutput,
                                                InterfaceState, SpeechResult]:
    """Un tour vocal complet : STT → boucle → TTS de la réponse validée."""
    recognized = transcribe(audio_ref, stt_fn,
                            timestamp=float(now)
                            if isinstance(now, (int, float)) else 0.0)
    if recognized.status == "FAILED":
        ui = InterfaceState(voice_state="ERROR",
                            last_response_kind="ERROR",
                            verified_success=False,
                            last_error="reconnaissance-indisponible")
        base = live if isinstance(live, LiveSession) else live
        return base, LoopResult(kind="ERROR", detail="stt-indisponible"), \
            SpeechOutput(status="SKIPPED", reason="pas-de-reponse"), ui, \
            recognized
    if not isinstance(live, LiveSession):
        opened_ok, live = open_session(
            session_id if isinstance(session_id, str) and session_id
            else "voix")
        if not opened_ok:
            ui = InterfaceState(voice_state="ERROR",
                                last_response_kind="ERROR",
                                verified_success=False,
                                last_error="session-invalide")
            return live, LoopResult(kind="ERROR",
                                    detail="session-invalide"), \
                SpeechOutput(status="SKIPPED", reason="pas-de-reponse"), ui, \
                recognized
    live, result = submit_turn(
        live, gate, recognized.text, now=now, source="voice",
        search_fn=search_fn, memory=memory, memorize=memorize,
        router_fn=router_fn, mandates=mandates, journal=journal,
        payload=payload, catalog=catalog, skill_id=skill_id,
        skill_version=skill_version, expires_at=expires_at,
        session_id=session_id if session_id is not None else live.id,
        stt_confidence=recognized.confidence)
    response_text = result.response.text \
        if result.response is not None and isinstance(
            result.response.text, str) else ""
    if not response_text.strip():
        response_text = _announce(result)
    if not response_text.strip() or result.kind == "ERROR":
        spoken = SpeechOutput(status="SKIPPED", reason="pas-de-reponse")
    else:
        spoken = speak(response_text, synth_fn, play_fn=play_fn)
    ui = InterfaceState(
        voice_state="SPEAKING" if spoken.status == "SPOKEN" else "IDLE",
        last_response_kind=result.response.kind
        if result.response is not None else result.kind,
        verified_success=False, last_error="")
    return live, result, spoken, ui, recognized


def describe() -> dict:
    """Capacités vocales déclaratives (aucun moteur réel câblé)."""
    return {"pipeline": "audio→STT→live→TTS",
            "core_commun_texte_voix": True,
            "moteur_stt_reel": False,
            "moteur_tts_reel": False,
            "microphone_reel": False,
            "network": False, "authority": False}
