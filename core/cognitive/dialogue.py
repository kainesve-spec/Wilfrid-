"""Wilfrid — boucle dialogue gouvernée (décision conversationnelle, sans autorité).

Enchaîne, de façon pure et déterministe : tour brut → `run_turn()` (P5 +
dispatch existants) → décision dialogue → [recherche injectée] → réponse
structurée → mise à jour de contexte bornée. Ne crée ni permission ni
Approval, n'exécute rien, n'appelle ni Governor ni réseau : REQUIRE_CONFIRMATION
décrit une action en attente d'humain sans l'autoriser ; CLARIFY liste ce qui
manque sans deviner ; les statuts O2 incertains sont présentés tels quels,
jamais convertis en certitude. Dépendances : même paquet cognitif +
constantes inertes `core.p7.types` (risques) ; recherche via callable injecté
(aucun import knowledge : séparation des couches).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.cognitive.session_input import TurnResult, run_turn
from core.cognitive.types import IntentKind
from core.p7.types import RISK_OF

MAX_HISTORY_TURNS = 10
MAX_TEXT_CHARS = 2000

RESPONSE_KINDS = (
    "CLARIFY",
    "REQUIRE_CONFIRMATION",
    "ANSWER",
    "REFUSE",
    "ERROR",
    "CONTINUE",
)

_UNCERTAIN_O2 = ("LOW_CONFIDENCE", "CONTRADICTORY", "AMBIGUOUS", "NO_SOURCE",
                 "NO_MATCH", "PARTIAL", "UNVERIFIED", "DEFERRED", "DENIED",
                 "FAILED")


@dataclass(frozen=True)
class PendingConfirmation:
    """Action R1/R2 en attente d'humain : description seule, sans autorisation."""

    request_id: str = ""
    permission_id: str = ""
    scope: str = ""
    target: str = ""
    reason: str = ""


@dataclass(frozen=True)
class DialogueResponse:
    """Réponse structurée : gabarits fermés + données vérifiées uniquement."""

    kind: str = "ERROR"
    text: str = ""
    missing: Tuple[str, ...] = ()
    pending: Optional[PendingConfirmation] = None


@dataclass(frozen=True)
class DialogueState:
    """État conversationnel borné : historique + attente éventuelle + compteur."""

    history: Tuple[Dict[str, Any], ...] = ()
    pending: Optional[PendingConfirmation] = None
    turn_index: int = 0


def _short_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def _bounded(history: Tuple[Dict[str, Any], ...],
             turn: Dict[str, Any]) -> Tuple[Dict[str, Any], ...]:
    updated = history + (turn,)
    if len(updated) > MAX_HISTORY_TURNS:
        updated = updated[-MAX_HISTORY_TURNS:]
    return updated


def _ack_text(kind: str, uncertainty: str, answer: str) -> str:
    if kind == "SUCCESS":
        return f"Réponse : {answer}"
    if kind in _UNCERTAIN_O2:
        detail = uncertainty or kind
        body = f" — {answer}" if answer else ""
        return f"Incertain ({detail}){body}"
    return f"Sans réponse ({kind})"


def respond(state: Any, text: Any, *, session_id: Any, now: Any,
            source: Any, search_fn: Optional[Callable] = None,
            skill_id: str = "wilfrid-core",
            skill_version: str = "1.0",
            stt_confidence: Optional[float] = None
            ) -> Tuple[DialogueState, DialogueResponse]:
    """Un tour complet : interprétation → décision → réponse → contexte."""
    if not isinstance(state, DialogueState):
        state = DialogueState()
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
        response = DialogueResponse(
            kind="CLARIFY", text="Précisez : texte-vide.",
            missing=("texte-vide",))
        return DialogueState(history=_bounded(state.history, {
            "role": "user", "text": ""}), pending=None,
            turn_index=state.turn_index + 1), response
    user_turn = {"role": "user", "text": text.strip()}
    history = _bounded(state.history, user_turn)
    rid = f"dlg-{_short_id(str(session_id), str(state.turn_index), text)}"
    try:
        turn_result = run_turn(
            [dict(turn) for turn in history], session_id, now, source,
            skill_id=skill_id, skill_version=skill_version, request_id=rid,
            stt_confidence=stt_confidence)
    except Exception:
        response = DialogueResponse(kind="ERROR", text="Erreur technique.")
        return DialogueState(history=history, pending=None,
                             turn_index=state.turn_index + 1), response
    output = turn_result.cognitive_output
    kind = output.kind if output is not None else None
    if kind == IntentKind.REFUSE:
        response = DialogueResponse(kind="REFUSE", text="Refusé.")
        return DialogueState(history=_bounded(history, {
            "role": "wilfrid", "text": response.text}), pending=None,
            turn_index=state.turn_index + 1), response
    if kind in (IntentKind.CLARIFY, IntentKind.UNCERTAIN) or (
            turn_result.status == "NO_ROUTE" and kind in (
                IntentKind.DIRECT, IntentKind.PLAN)):
        if kind in (IntentKind.DIRECT, IntentKind.PLAN):
            response = DialogueResponse(kind="CONTINUE", text="Bien reçu.")
            return DialogueState(history=_bounded(history, {
                "role": "wilfrid", "text": response.text}), pending=None,
                turn_index=state.turn_index + 1), response
        missing = tuple(getattr(output, "missing", None) or ())
        if not missing:
            missing = ("intention-ambiguë",)
        response = DialogueResponse(
            kind="CLARIFY",
            text="Précisez : " + ", ".join(missing[:8]) + ".",
            missing=tuple(m[:64] for m in missing[:8]))
        return DialogueState(history=_bounded(history, {
            "role": "wilfrid", "text": response.text}), pending=None,
            turn_index=state.turn_index + 1), response
    if kind == IntentKind.NEED_SEARCH:
        if search_fn is None:
            response = DialogueResponse(
                kind="REFUSE", text="Refusé : recherche non disponible.")
            return DialogueState(history=_bounded(history, {
                "role": "wilfrid", "text": response.text}), pending=None,
                turn_index=state.turn_index + 1), response
        try:
            result = search_fn(output)
        except Exception:
            result = None
        if result is None or not isinstance(
                getattr(result, "status", None), str):
            response = DialogueResponse(kind="ERROR", text="Erreur technique.")
            return DialogueState(history=_bounded(history, {
                "role": "wilfrid", "text": response.text}), pending=None,
                turn_index=state.turn_index + 1), response
        response = DialogueResponse(
            kind="ANSWER",
            text=_ack_text(str(result.status),
                           str(getattr(result, "uncertainty", "") or ""),
                           str(getattr(result, "answer", "") or "")))
        return DialogueState(history=_bounded(history, {
            "role": "wilfrid", "text": response.text}), pending=None,
            turn_index=state.turn_index + 1), response
    if turn_result.status == "ROUTED" and turn_result.dispatch_result is not None \
            and turn_result.dispatch_result.request is not None:
        request = turn_result.dispatch_result.request
        risk = RISK_OF.get(request.permission_id, "R3")
        if risk in ("R1", "R2", "R3", "R4"):
            pending = PendingConfirmation(
                request_id=request.request_id,
                permission_id=request.permission_id,
                scope=request.scope, target=request.target,
                reason="confirmation-humaine-requise")
            response = DialogueResponse(
                kind="REQUIRE_CONFIRMATION",
                text=f"Confirmation requise : {request.permission_id} "
                     f"sur {request.target}.",
                pending=pending)
            return DialogueState(history=_bounded(history, {
                "role": "wilfrid", "text": response.text}), pending=pending,
                turn_index=state.turn_index + 1), response
        response = DialogueResponse(kind="CONTINUE", text="Bien reçu.")
        return DialogueState(history=_bounded(history, {
            "role": "wilfrid", "text": response.text}), pending=None,
            turn_index=state.turn_index + 1), response
    response = DialogueResponse(kind="REFUSE", text="Refusé : non pris en charge.")
    return DialogueState(history=_bounded(history, {
        "role": "wilfrid", "text": response.text}), pending=None,
        turn_index=state.turn_index + 1), response
