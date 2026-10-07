"""Wilfrid — boucle textuelle gouvernée (intégration, sans autorité propre).

Enchaîne les composants qualifiés existants, sans les réécrire :
texte → Dialogue (`respond`) → [recherche injectée] → REQUIRE_CONFIRMATION →
Approval Gate (humain) → `invoke` P7 → vérification indépendante → réponse
honnête → mémoire explicite optionnelle.

Règles : intention ≠ autorisation ; approbation liée à la demande exacte
(empreinte) ; DENY/EXPIRED/CONSUMED = zéro effet ; vérification indépendante
de l'appel (VERIFIED_SUCCESS/FAILED/UNCERTAIN, jamais de succès supposé) ;
mémoire = notes explicites uniquement, jamais d'autorisation. Aucun mandat
automatique : sans mécanisme de mandat implémenté, tout effet passe par
confirmation humaine (R2 non démontrable, déclaré comme tel).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.cognitive.dialogue import DialogueResponse, DialogueState, respond
from core.cognitive.dialogue import PendingConfirmation
from core.memory.continuity import record_turn
from core.p7.approval_gate import ApprovalGate, demand_fingerprint
from core.p7.invoke import invoke
from core.p7.notify import expected_target
from core.p7.resolver import jail_root, resolve as resolve_path
from core.p7.types import Approval, MAX_DURATION_S, MAX_LIMITS, Request

LOOP_KINDS = (
    "RESPONDED",
    "CONFIRM_CREATED",
    "CONFIRM_RESOLVED",
    "REFUSED",
    "ERROR",
)

VERIFICATIONS = ("VERIFIED_SUCCESS", "FAILED", "UNCERTAIN", "")


@dataclass(frozen=True)
class LoopResult:
    """Issue d'un pas de boucle : traçable par request/confirmation_id."""

    kind: str = "ERROR"
    response: Optional[DialogueResponse] = None
    request_id: str = ""
    confirmation_id: str = ""
    verification: str = ""
    memory_ok: bool = True
    detail: str = ""
    request: Any = None


def _context_hash(session_id: Any, turn_index: Any) -> str:
    return hashlib.sha256(
        f"{session_id}|{turn_index}".encode("utf-8")).hexdigest()[:32]


def _confirmation_id(fingerprint: str, session_id: Any,
                     turn_index: Any) -> str:
    seed = f"{fingerprint}|{session_id}|{turn_index}".encode("utf-8")
    return "cfm-" + hashlib.sha256(seed).hexdigest()[:12]


def _demand_fp(request: Any, context_hash: str) -> str:
    limits = request.limits if isinstance(request.limits, dict) else {}
    return demand_fingerprint(
        request_id=request.request_id, permission_id=request.permission_id,
        scope=request.scope, target=request.target, limits=limits,
        context_hash=context_hash)


def _router_request(route: Any, request_id: str) -> Optional[Request]:
    """Construit une vraie Request depuis un RouteResult MATCH, ou None.

    Cibles confinées uniquement (resolver) : tout échec retombe sur le
    chemin dialogue existant, jamais de demande fabriquée.
    """
    from core.p7.catalog import scope_for

    capability_id = getattr(route, "capability_id", "")
    params = getattr(route, "params", None)
    if capability_id not in MAX_LIMITS or not isinstance(params, dict):
        return None
    if capability_id == "P7.CATALOG_READ":
        scope, target = scope_for(capability_id), capability_id
    elif capability_id in ("P7.JAIL_READ", "P7.JAIL_WRITE_REVERSIBLE"):
        filename = params.get("filename", "")
        if not isinstance(filename, str) or not filename:
            return None
        target = str(jail_root() / filename)
        scope = (f"fichier:{target}:lecture-seule"
                 if capability_id == "P7.JAIL_READ"
                 else f"fichier:{target}:écriture-réversible-bornée")
        ok, _, _ = resolve_path(scope, target)
        if not ok:
            return None
    elif capability_id == "P7.NOTIFY_LOCAL":
        target = expected_target(request_id)
        scope = f"notification:{target}:textuel-borné"
        ok, _, _ = resolve_path(scope, target)
        if not ok:
            return None
    else:
        return None
    return Request(
        request_id=request_id, skill_id="wilfrid-core", skill_version="1.0",
        permission_id=capability_id, scope=scope, target=target,
        limits=dict(MAX_LIMITS[capability_id]),
        duration_s=int(MAX_DURATION_S.get(capability_id, 0)),
        reason="routeur-intention")


def _router_pending(request: Any) -> PendingConfirmation:
    return PendingConfirmation(
        request_id=request.request_id, permission_id=request.permission_id,
        scope=request.scope, target=request.target,
        reason="routeur-intention")
def request_confirmation(gate: Any, request: Any, session_id: Any,
                         turn_index: Any, now: Any,
                         expires_at: Any = None) -> Tuple[bool, str]:
    """Crée la demande PENDING pour une requête exacte. Sans effet."""
    if not isinstance(gate, ApprovalGate):
        return False, "gate-invalide"
    permission_id = getattr(request, "permission_id", None)
    scope = getattr(request, "scope", None)
    target = getattr(request, "target", None)
    request_id = getattr(request, "request_id", None)
    for value in (permission_id, scope, target, request_id):
        if not isinstance(value, str) or not value.strip():
            return False, "requete-invalide"
    context_hash = _context_hash(session_id, turn_index)
    fingerprint = _demand_fp(request, context_hash)
    confirmation_id = _confirmation_id(fingerprint, session_id, turn_index)
    ok, created = gate.create_confirmation(
        confirmation_id, request_id, permission_id, scope, target,
        limits=request.limits if isinstance(request.limits, dict) else {},
        context_hash=context_hash, expires_at=expires_at, now=now)
    if not ok:
        return False, str(created)
    return True, confirmation_id


def verify_effect(permission_id: Any, request: Any, result: Any,
                  payload: Any = None) -> str:
    """Vérifie un effet par relecture indépendante. Jamais de succès supposé."""
    try:
        if permission_id == "P7.CATALOG_READ":
            if not isinstance(result, dict):
                return "FAILED"
            return "VERIFIED_SUCCESS" if result.get("id") == \
                request.permission_id else "FAILED"
        target = getattr(request, "target", "")
        scope = getattr(request, "scope", "")
        ok, _, path = resolve_path(scope, target)
        if not ok or path is None:
            return "UNCERTAIN"
        if permission_id == "P7.JAIL_READ":
            if not isinstance(result, (bytes, bytearray)):
                return "FAILED"
            try:
                observed = path.read_bytes()
            except OSError:
                return "UNCERTAIN"
            return "VERIFIED_SUCCESS" if observed == bytes(result) else "FAILED"
        if permission_id == "P7.JAIL_WRITE_REVERSIBLE":
            if not isinstance(payload, (bytes, bytearray)):
                return "FAILED"
            try:
                observed = path.read_bytes()
            except OSError:
                return "UNCERTAIN"
            return "VERIFIED_SUCCESS" if observed == bytes(payload) else "FAILED"
        if permission_id == "P7.NOTIFY_LOCAL":
            try:
                expected = expected_target(request.request_id)
            except Exception:
                return "UNCERTAIN"
            if str(path) != str(expected):
                return "FAILED"
            try:
                observed = path.read_text(encoding="utf-8")
            except OSError:
                return "UNCERTAIN"
            if not isinstance(payload, str):
                return "FAILED"
            return "VERIFIED_SUCCESS" if observed == payload else "FAILED"
        return "UNCERTAIN"
    except Exception:
        return "UNCERTAIN"


def _memorize_turns(memory: Any, session_id: Any, turn_index: Any,
                    user_text: str, response_text: str) -> bool:
    if memory is None:
        return True
    try:
        base = f"dlg-{session_id}-{turn_index}"
        ok_user, _ = record_turn(memory, f"{base}-user", "user", user_text,
                                 session_id=str(session_id))
        ok_wilfrid, _ = record_turn(memory, f"{base}-wilfrid", "wilfrid",
                                    response_text, session_id=str(session_id))
        return bool(ok_user and ok_wilfrid)
    except Exception:
        return False


def run_text_turn(state: Any, gate: Any, text: Any, *, session_id: Any,
                  now: Any, source: str = "text", search_fn: Any = None,
                  memory: Any = None, memorize: bool = False,
                  skill_id: str = "wilfrid-core",
                  skill_version: str = "1.0",
                  expires_at: Any = None,
                  router_fn: Any = None) -> Tuple[DialogueState, LoopResult]:
    """Un tour : dialogue → éventuelle demande PENDING → réponse + mémoire.

    `router_fn` optionnel (interprétation/routage uniquement) : si le dialogue
    ne produit pas déjà REQUIRE_CONFIRMATION et que le routeur retourne un
    MATCH complet, la demande est créée via le même Approval Gate. Sinon le
    chemin dialogue existant s'applique, inchangé.
    """
    new_state, response = respond(
        state, text, session_id=session_id, now=now, source=source,
        search_fn=search_fn, skill_id=skill_id, skill_version=skill_version)
    memory_ok = True
    if memorize and memory is not None and isinstance(text, str) \
            and text.strip():
        memory_ok = _memorize_turns(memory, session_id,
                                    new_state.turn_index, text.strip(),
                                    response.text)
    if response.kind != "REQUIRE_CONFIRMATION" or response.pending is None:
        if router_fn is not None and isinstance(text, str) and text.strip():
            try:
                routed = router_fn(text)
            except Exception:
                routed = None
            if routed is not None and getattr(routed, "status", "") == "MATCH":
                rid = "rt-" + hashlib.sha256(
                    f"{session_id}|{new_state.turn_index}|{text}".encode(
                        "utf-8")).hexdigest()[:12]
                shaped = _router_request(routed, rid)
                if shaped is not None:
                    pending = _router_pending(shaped)
                    response = DialogueResponse(
                        kind="REQUIRE_CONFIRMATION",
                        text="Confirmation requise : "
                             f"{shaped.permission_id} sur {shaped.target}.",
                        pending=pending)
                    created_state, created = _confirm_created(
                        gate, new_state, response, shaped, session_id, now,
                        memory_ok, memory, expires_at)
                    if created.kind == "CONFIRM_CREATED":
                        created = LoopResult(
                            kind=created.kind, response=created.response,
                            request_id=created.request_id,
                            confirmation_id=created.confirmation_id,
                            verification=created.verification,
                            memory_ok=created.memory_ok,
                            detail=created.detail, request=shaped)
                    return created_state, created
        kind = "RESPONDED" if response.kind != "ERROR" else "ERROR"
        return new_state, LoopResult(
            kind=kind, response=response, memory_ok=memory_ok,
            detail=response.kind)
def _confirm_created(gate: Any, new_state: DialogueState,
                     response: DialogueResponse, shaped: Any,
                     session_id: Any, now: Any, memory_ok: bool,
                     memory: Any, expires_at: Any) -> Tuple[DialogueState, LoopResult]:
    """Crée la demande PENDING via l'Approval Gate. Sans effet."""
    ok, confirmation_id = request_confirmation(
        gate, shaped, session_id, new_state.turn_index, now,
        expires_at=expires_at)
    if not ok:
        return new_state, LoopResult(
            kind="ERROR", response=response, memory_ok=memory_ok,
            detail=str(confirmation_id))
    return new_state, LoopResult(
        kind="CONFIRM_CREATED", response=response,
        request_id=shaped.request_id,
        confirmation_id=str(confirmation_id), memory_ok=memory_ok,
        detail="pending")


    # Chemin dialogue historique (P7.1 PASS, inchangé) : pending existant.
    pending = response.pending
    request_id = getattr(pending, "request_id", "")
    scope = getattr(pending, "scope", "")
    target = getattr(pending, "target", "")
    permission_id = getattr(pending, "permission_id", "")

    class _Shaped:
        pass
    shaped = _Shaped()
    shaped.request_id = request_id
    shaped.permission_id = permission_id
    shaped.scope = scope
    shaped.target = target
    shaped.limits = {}
    return _confirm_created(gate, new_state, response, shaped, session_id,
                            now, memory_ok, memory, expires_at)


def resolve_confirmation(gate: Any, confirmation_id: Any, decision: Any,
                         decided_by: Any, *, request: Any, session_id: Any,
                         turn_index: Any, now: Any, journal: Any,
                         payload: Any = None, catalog: Any = None,
                         memory: Any = None,
                         memorize: bool = False) -> LoopResult:
    """Résout une confirmation : DENY → refus ; APPROVE → consume → invoke → vérifie."""
    if decision not in ("APPROVE", "DENY"):
        return LoopResult(kind="ERROR", detail="decision-invalide")
    if not isinstance(gate, ApprovalGate):
        return LoopResult(kind="ERROR", detail="gate-invalide")
    context_hash = _context_hash(session_id, turn_index)
    fingerprint = _demand_fp(request, context_hash) \
        if _shaped_request(request) else ""
    if decision == "DENY":
        ok, _ = gate.deny_confirmation(confirmation_id, decided_by,
                                        reason="refus-humain", now=now)
        return LoopResult(kind="REFUSED" if ok else "ERROR",
                          confirmation_id=str(confirmation_id),
                          detail="refuse" if ok else "refus-impossible")
    ok, _ = gate.approve_confirmation(confirmation_id, decided_by,
                                      fingerprint, now=now)
    if not ok:
        return LoopResult(kind="REFUSED", confirmation_id=str(confirmation_id),
                          detail="approbation-refusee")
    ok, consumed = gate.consume_confirmation(confirmation_id, fingerprint,
                                             now=now)
    if not ok or not hasattr(consumed, "scope"):
        return LoopResult(kind="REFUSED", confirmation_id=str(confirmation_id),
                          detail="consommation-refusee")
    duration = getattr(request, "duration_s", 0)
    if not isinstance(duration, int) or isinstance(duration, bool) \
            or duration <= 0:
        duration = 0
    approval = Approval(
        request_id=consumed.request_id, permission_id=consumed.permission_id,
        decision="accorde", scope=consumed.scope,
        duration_s=duration,
        reason=f"approval-gate:{confirmation_id}",
        capability_version=1, timestamp=float(now)
        if isinstance(now, (int, float)) else 0.0)
    invoked = invoke(permission_id=consumed.permission_id, request=request,
                     approval=approval, now=now, journal=journal,
                     payload=payload, catalog=catalog)
    if invoked.decision is None or not invoked.decision.allowed:
        return LoopResult(kind="REFUSED", request_id=consumed.request_id,
                          confirmation_id=str(confirmation_id),
                          detail="gouverneur-refuse")
    verification = verify_effect(consumed.permission_id, request,
                                 invoked.result, payload)
    memory_ok = True
    if memorize and memory is not None:
        memory_ok = _memorize_turns(memory, session_id, turn_index,
                                    f"effet {consumed.permission_id} "
                                    f"{verification}",
                                    f"resultat: {verification}")
    return LoopResult(kind="CONFIRM_RESOLVED", request_id=consumed.request_id,
                      confirmation_id=str(confirmation_id),
                      verification=verification, memory_ok=memory_ok,
                      detail=verification)


def _shaped_request(request: Any) -> bool:
    for attr in ("request_id", "permission_id", "scope", "target"):
        value = getattr(request, attr, None)
        if not isinstance(value, str) or not value.strip():
            return False
    return True
