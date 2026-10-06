"""Wilfrid — décideur P5 (cohérence sans effets).

Règles : information manquante → CLARIFY ; intention incertaine →
UNCERTAIN (déjà classée) ; demande interdite → REFUSE (déjà classée).
Normalise : confiance dans [0,1], payload borné, missing borné.
Aucune décision ne provoque d'effet externe.
"""

from __future__ import annotations

from core.cognitive.types import (
    CognitiveInput,
    CognitiveOutput,
    CognitiveParams,
    IntentKind,
)

MAX_MISSING = 8
MAX_FIELD_CHARS = 200
MAX_STEP_CHARS = 80  # aligné sur planner.MAX_STEP_CHARS (contrat de sortie)
MAX_STEPS = 8


def _clip(text: str, limit: int = MAX_FIELD_CHARS) -> str:
    text = str(text or "")
    return text[:limit]


def _bounded_params(params: CognitiveParams) -> CognitiveParams:
    steps = [str(s)[:MAX_STEP_CHARS] for s in list(params.etapes)[:MAX_STEPS]]
    return CognitiveParams(
        action=_clip(params.action),
        objet=_clip(params.objet),
        cible=_clip(params.cible),
        question=_clip(params.question),
        etapes=steps,
        outil=_clip(params.outil),
        besoin_recherche=_clip(params.besoin_recherche),
    )


def decide(classification: CognitiveOutput,
           _input: CognitiveInput) -> CognitiveOutput:
    """Rend la classification cohérente et bornée. Pure, déterministe."""
    kind = classification.kind
    missing = [str(m)[:64] for m in list(classification.missing)[:MAX_MISSING]]
    confidence = classification.confidence
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence != confidence:  # NaN
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))
    params = _bounded_params(classification.params)
    if missing and kind not in (IntentKind.CLARIFY,):
        # Information manquante avérée : la décision devient clarification,
        # en conservant la nature détectée dans les paramètres.
        return CognitiveOutput(IntentKind.CLARIFY, params, confidence, missing)
    return CognitiveOutput(kind, params, confidence, missing)
