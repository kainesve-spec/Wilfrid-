"""Wilfrid — tour audio réel → boucle vivante (interface, sans autorité).

Chemin obligatoire uniquement :
capture → transcribe → `LiveSession.submit_turn()` → Core/Governance
existants → réponse ou demande de confirmation → TTS → sortie.

Aucun raccourci vers `invoke()`, l'Approval Gate ou les mandats : ce module
reçoit `gate`/`mandates` en paramètres et les transmet à `voice_turn`, sans
jamais créer d'approbation, de registre ni de mandat. Capture en échec =
aucune soumission au Core, session inchangée.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from core.loop.live import LiveSession
from core.loop.loop import LoopResult
from core.voice.audio_backends import AudioCapture, run_capture
from core.voice.interaction import InterfaceState, SpeechOutput
from core.voice.live_voice import voice_turn


@dataclass(frozen=True)
class AudioTurnReport:
    """Rapport par étape : capture, STT, Core, TTS. États, jamais de promesse."""

    capture_status: str = "FAILED"
    capture_reason: str = "moteur-absent"
    capture_backend: str = ""
    stt_status: str = "FAILED"
    stt_confidence: Any = None
    core_kind: str = "ERROR"
    core_detail: str = ""
    tts_status: str = "SKIPPED"
    tts_reason: str = ""
    session_id: str = ""
    verified: bool = False


def audio_turn(live: Any, gate: Any, *, capture_fn: Any = None,
               stt_fn: Any = None, now: Any,
               max_seconds: Any = None, max_bytes: Any = None,
               sample_rate: Any = None, synth_fn: Any = None,
               play_fn: Any = None, search_fn: Any = None,
               memory: Any = None, memorize: bool = False,
               router_fn: Any = None, mandates: Any = None,
               journal: Any = None, payload: Any = None,
               catalog: Any = None, skill_id: str = "wilfrid-core",
               skill_version: str = "1.0", expires_at: Any = None,
               session_id: Any = None) -> Tuple[Any, LoopResult, SpeechOutput,
                                                InterfaceState,
                                                AudioTurnReport]:
    """Tour audio complet : capture bornée → STT → boucle → TTS validé."""
    from core.voice.audio_backends import (
        DEFAULT_SAMPLE_RATE,
        MAX_CAPTURE_BYTES,
        MAX_CAPTURE_SECONDS,
    )
    bounds: dict = {}
    if max_seconds is not None:
        bounds["max_seconds"] = max_seconds
    else:
        bounds["max_seconds"] = MAX_CAPTURE_SECONDS
    if max_bytes is not None:
        bounds["max_bytes"] = max_bytes
    else:
        bounds["max_bytes"] = MAX_CAPTURE_BYTES
    if sample_rate is not None:
        bounds["sample_rate"] = sample_rate
    else:
        bounds["sample_rate"] = DEFAULT_SAMPLE_RATE
    capture: AudioCapture = run_capture(capture_fn, **bounds)
    session_label = live.id if isinstance(live, LiveSession) else ""
    if capture.status != "OK":
        ui = InterfaceState(voice_state="ERROR",
                            last_response_kind="ERROR",
                            verified_success=False,
                            last_error="capture-indisponible")
        report = AudioTurnReport(
            capture_status="FAILED", capture_reason=capture.reason,
            capture_backend=capture.backend, stt_status="FAILED",
            core_kind="ERROR", core_detail="capture-indisponible",
            tts_status="SKIPPED", tts_reason="pas-de-reponse",
            session_id=session_label, verified=False)
        return live, LoopResult(kind="ERROR",
                                detail="capture-indisponible"), \
            SpeechOutput(status="SKIPPED", reason="pas-de-reponse"), ui, \
            report
    live, result, spoken, ui, recognized = voice_turn(
        live, gate, capture.pcm, stt_fn, now=now, synth_fn=synth_fn,
        play_fn=play_fn, search_fn=search_fn, memory=memory,
        memorize=memorize, router_fn=router_fn, mandates=mandates,
        journal=journal, payload=payload, catalog=catalog,
        skill_id=skill_id, skill_version=skill_version,
        expires_at=expires_at, session_id=session_id)
    verified = getattr(result, "verification", "") == "VERIFIED_SUCCESS"
    report = AudioTurnReport(
        capture_status="OK", capture_reason="",
        capture_backend=capture.backend, stt_status=recognized.status,
        stt_confidence=recognized.confidence, core_kind=result.kind,
        core_detail=result.detail or "", tts_status=spoken.status,
        tts_reason=spoken.reason or "",
        session_id=live.id if isinstance(live, LiveSession)
        else session_label, verified=verified)
    return live, result, spoken, ui, report


def describe() -> dict:
    """Pipeline audio déclaratif (aucun moteur réel câblé ici)."""
    return {"pipeline": "capture→STT→live→TTS",
            "core_commun_texte_voix": True,
            "soumission_sans_capture": False,
            "network": False, "authority": False}
