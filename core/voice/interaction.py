"""Wilfrid — voix et interface gouvernées (Master 7) : états sans autorité.

Fournit : machine d'états vocaux (IDLE/LISTENING/PROCESSING/SPEAKING/ERROR),
adaptateurs STT/TTS à fonctions injectées (aucun moteur câblé, aucun réseau),
câblage voix/texte → même pipeline Dialogue, état d'interface dérivé du réel,
et visualiseur circulaire minimal purement calculé (aucun toolkit).

Règles : l'interface ne décide ni n'autorise rien ; le STT produit une entrée
(texte + confiance, jamais d'intention autorisée) ; le TTS restitue une réponse
déjà validée (jamais une preuve d'exécution) ; une commande vocale suit
exactement le même pipeline qu'une commande texte ; l'UI n'affiche « réussi »
que sur succès vérifié explicite ; aucune ambiguïté résolue par supposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.cognitive.dialogue import DialogueResponse, DialogueState, respond

VOICE_STATES = ("IDLE", "LISTENING", "PROCESSING", "SPEAKING", "ERROR")

_VOICE_TRANSITIONS = {
    "IDLE": ("LISTENING", "ERROR"),
    "LISTENING": ("PROCESSING", "ERROR", "IDLE"),
    "PROCESSING": ("SPEAKING", "ERROR", "IDLE"),
    "SPEAKING": ("IDLE", "ERROR"),
    "ERROR": ("IDLE",),
}

STT_STATUSES = ("OK", "UNCERTAIN", "FAILED")
TTS_STATUSES = ("SPOKEN", "SKIPPED", "FAILED")

VISUAL_BANDS = 3


@dataclass(frozen=True)
class SpeechResult:
    """Sortie STT : texte reconnu + confiance + source, jamais une intention."""

    text: str = ""
    confidence: Optional[float] = None
    source: str = ""
    timestamp: float = 0.0
    status: str = "FAILED"


@dataclass(frozen=True)
class SpeechOutput:
    """Sortie TTS : statut de restitution d'une réponse déjà validée."""

    text: str = ""
    status: str = "SKIPPED"
    reason: str = ""


@dataclass(frozen=True)
class InterfaceState:
    """État affiché, dérivé du réel uniquement."""

    voice_state: str = "IDLE"
    last_response_kind: str = ""
    verified_success: bool = False
    last_error: str = ""


def voice_transition(current: Any, target: Any) -> Tuple[bool, str]:
    """Transition vocale explicite. États inconnus ou interdits = refus."""
    if current not in _VOICE_TRANSITIONS:
        return False, "etat-inconnu"
    if not isinstance(target, str) or target not in _VOICE_TRANSITIONS[current]:
        return False, "transition-invalide"
    return True, "ok"


def transcribe(audio_ref: Any, stt_fn: Any = None, *,
               timestamp: float = 0.0) -> SpeechResult:
    """Transcrit via fonction injectée. Sans moteur : échec explicite."""
    if stt_fn is None or not callable(stt_fn):
        return SpeechResult(status="FAILED")
    try:
        produced = stt_fn(audio_ref)
    except Exception:
        return SpeechResult(status="FAILED")
    if not isinstance(produced, (tuple, list)) or len(produced) != 2:
        return SpeechResult(status="FAILED")
    text, confidence = produced
    if not isinstance(text, str) or not text.strip():
        return SpeechResult(status="UNCERTAIN")
    if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= float(confidence) <= 1.0):
        return SpeechResult(status="FAILED")
    if len(text.strip()) > 2000:
        return SpeechResult(status="FAILED")
    moment = float(timestamp) if isinstance(timestamp,
                                            (int, float)) else 0.0
    return SpeechResult(text=text.strip(), confidence=None
                        if confidence is None else float(confidence),
                        source="stt", timestamp=moment, status="OK")


def speak(response_text: Any, synth_fn: Any = None,
          play_fn: Any = None) -> SpeechOutput:
    """Restitue une réponse validée via fonctions injectées. Sans synthèse : saut."""
    if not isinstance(response_text, str) or not response_text.strip():
        return SpeechOutput(status="SKIPPED", reason="texte-vide")
    if synth_fn is None or not callable(synth_fn):
        return SpeechOutput(text=response_text.strip(), status="SKIPPED",
                            reason="tts-indisponible")
    try:
        audio = synth_fn(response_text.strip())
    except Exception:
        return SpeechOutput(text=response_text.strip(), status="FAILED",
                            reason="synthese-impossible")
    if not isinstance(audio, (bytes, bytearray)) or not bytes(audio):
        return SpeechOutput(text=response_text.strip(), status="FAILED",
                            reason="audio-invalide")
    if play_fn is not None:
        if not callable(play_fn):
            return SpeechOutput(text=response_text.strip(), status="FAILED",
                                reason="lecture-impossible")
        try:
            play_fn(bytes(audio))
        except Exception:
            return SpeechOutput(text=response_text.strip(), status="FAILED",
                                reason="lecture-impossible")
    return SpeechOutput(text=response_text.strip(), status="SPOKEN",
                        reason="ok")


def handle_text_turn(state: Any, text: Any, *, session_id: Any, now: Any,
                     search_fn: Any = None) -> Tuple[DialogueState, DialogueResponse,
                                                     InterfaceState]:
    """Tour texte : même pipeline Dialogue, état IDLE dérivé du résultat."""
    new_state, response = respond(
        state, text, session_id=session_id, now=now, source="text",
        search_fn=search_fn)
    ui = InterfaceState(voice_state="IDLE",
                        last_response_kind=response.kind,
                        verified_success=False, last_error="")
    return new_state, response, ui


def handle_voice_turn(state: Any, audio_ref: Any, stt_fn: Any = None, *,
                      session_id: Any, now: Any,
                      search_fn: Any = None) -> Tuple[DialogueState, DialogueResponse,
                                                      InterfaceState]:
    """Tour vocal : STT puis exactement le même pipeline que le texte."""
    recognized = transcribe(audio_ref, stt_fn,
                            timestamp=float(now)
                            if isinstance(now, (int, float)) else 0.0)
    if recognized.status == "FAILED":
        ui = InterfaceState(voice_state="ERROR",
                            last_response_kind="ERROR",
                            verified_success=False,
                            last_error="reconnaissance-indisponible")
        base = state if isinstance(state, DialogueState) else DialogueState()
        return base, DialogueResponse(kind="ERROR",
                                      text="Erreur technique."), ui
    new_state, response = respond(
        state, recognized.text, session_id=session_id, now=now,
        source="voice", search_fn=search_fn,
        stt_confidence=recognized.confidence)
    ui = InterfaceState(voice_state="IDLE",
                        last_response_kind=response.kind,
                        verified_success=False, last_error="")
    return new_state, response, ui


def mark_verified_success(ui: Any) -> InterfaceState:
    """Ne marque un succès vérifié que sur décision externe explicite."""
    if not isinstance(ui, InterfaceState):
        return InterfaceState()
    return InterfaceState(voice_state=ui.voice_state,
                          last_response_kind=ui.last_response_kind,
                          verified_success=True,
                          last_error=ui.last_error)


def rings(level: Any, voice_state: Any, phase: Any,
          bands: int = VISUAL_BANDS) -> Tuple[float, ...]:
    """Anneaux concentriques : amplitude par bande, 100 % déterministe.

    `phase` (fournie par l'appelant) anime PROCESSING/SPEAKING sans horloge
    interne. IDLE/ERROR = silence. Sortie bornée [0, 1], prête pour un rendu
    ultérieur (aucun toolkit ici).
    """
    try:
        count = int(bands)
    except (TypeError, ValueError):
        return ()
    if not 1 <= count <= 8:
        return ()
    try:
        amplitude = max(0.0, min(1.0, float(level)))
    except (TypeError, ValueError):
        return ()
    try:
        angle = float(phase)
    except (TypeError, ValueError):
        angle = 0.0
    if voice_state == "IDLE" or voice_state == "ERROR":
        return tuple(0.0 for _ in range(count))
    if voice_state not in ("LISTENING", "PROCESSING", "SPEAKING"):
        return tuple(0.0 for _ in range(count))
    import math
    values = []
    for index in range(count):
        if voice_state == "LISTENING":
            values.append(round(amplitude, 3))
        else:
            wave = (math.sin(angle + index * math.pi / count) + 1.0) / 2.0
            values.append(round(amplitude * wave, 3))
    return tuple(values)


def describe() -> Dict[str, Any]:
    """Capacités de la couche (déclaratif, sans effet)."""
    return {"voice_states": list(VOICE_STATES),
            "stt_statuses": list(STT_STATUSES),
            "tts_statuses": list(TTS_STATUSES),
            "visual_bands": VISUAL_BANDS,
            "network": False, "authority": False}
