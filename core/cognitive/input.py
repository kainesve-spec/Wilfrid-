"""Wilfrid — construction validée de CognitiveInput (P5).

Validation explicite : texte ≤ 2000c, session_id/timestamp/source
obligatoires, contexte borné. Copie PROFONDE obligatoire du contexte
source (norme P5 ; une copie superficielle est interdite).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from core.cognitive.types import MAX_TEXT_CHARS, CognitiveInput


class CognitiveInputError(ValueError):
    """Entrée invalide : refus explicite, jamais de devinette."""


def build_input(text: str, session_id: str,
                context_snapshot: List[Dict[str, Any]], timestamp: float,
                source: str,
                stt_confidence: Optional[float] = None) -> CognitiveInput:
    if not isinstance(text, str):
        raise CognitiveInputError("text doit être une chaîne")
    # Texte vide accepté : c'est le classifieur qui émet CLARIFY.
    if len(text) > MAX_TEXT_CHARS:
        raise CognitiveInputError(
            f"texte {len(text)} > {MAX_TEXT_CHARS} caractères")
    if not isinstance(session_id, str) or not session_id:
        raise CognitiveInputError("session_id obligatoire non vide")
    if not isinstance(timestamp, (int, float)) or timestamp != timestamp:
        raise CognitiveInputError("timestamp fini obligatoire")
    if not isinstance(source, str) or not source:
        raise CognitiveInputError("source obligatoire non vide")
    if stt_confidence is not None and not (
            isinstance(stt_confidence, (int, float))
            and 0.0 <= float(stt_confidence) <= 1.0):
        raise CognitiveInputError("stt_confidence doit être dans [0,1]")
    if not isinstance(context_snapshot, list):
        raise CognitiveInputError("context_snapshot doit être une liste")
    snapshot = copy.deepcopy(context_snapshot)
    return CognitiveInput(
        text=text,
        session_id=session_id,
        context_snapshot=snapshot,
        timestamp=float(timestamp),
        source=source,
        stt_confidence=(None if stt_confidence is None
                        else float(stt_confidence)),
    )
