"""Wilfrid — session vivante textuelle (orchestration, sans autorité propre).

Enchaîne les composants qualifiés sans les réécrire : état de session fermé,
contexte borné (session + mémoire pertinente marquée), tours via la boucle
gouvernée existante, confirmations via l'Approval Gate, mandats R2 réévalués
à l'acte. N'ajoute aucune autorité : PENDING/APPROVE/DENY/CONSUME, révocation
et expiration restent intégralement du ressort du gate et des mandats ; ici,
seuls des états sont tenus et des refus sont opposés.

Règles : CLOSED/ERROR terminales (aucun nouveau tour) ; PAUSED bloque les
tours sensibles mais conserve tout ; WAITING_CONFIRMATION conserve la demande
exacte et refuse tout autre tour ; reprise ne restaure jamais une autorisation
(confirmations consommées/expirées et mandats révoqués restent inutilisables) ;
CONFIRM_CREATED ne prouve rien tant que la résolution n'a pas vérifié l'effet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.cognitive.dialogue import DialogueState
from core.loop.loop import LoopResult, resolve_confirmation, run_text_turn
from core.memory.continuity import recall_context
from core.p7.approval_gate import ApprovalGate

LIVE_STATES = (
    "NEW",
    "ACTIVE",
    "WAITING_CONFIRMATION",
    "PROCESSING",
    "PAUSED",
    "CLOSED",
    "ERROR",
)

_LIVE_TRANSITIONS = {
    "NEW": ("ACTIVE", "CLOSED", "ERROR"),
    "ACTIVE": ("PROCESSING", "PAUSED", "CLOSED", "ERROR",
               "WAITING_CONFIRMATION"),
    "PROCESSING": ("ACTIVE", "WAITING_CONFIRMATION", "CLOSED", "ERROR"),
    "WAITING_CONFIRMATION": ("ACTIVE", "CLOSED", "ERROR"),
    "PAUSED": ("ACTIVE", "CLOSED", "ERROR"),
    "CLOSED": (),
    "ERROR": (),
}

MAX_MEMORY_TURNS = 3


@dataclass(frozen=True)
class PendingDemand:
    """Demande exacte en attente : identifiants + champs de la requête."""

    confirmation_id: str = ""
    request_id: str = ""
    permission_id: str = ""
    scope: str = ""
    target: str = ""
    limits: Tuple[Tuple[str, str], ...] = ()
    duration_s: int = 0
    reason: str = ""


@dataclass(frozen=True)
class LiveSession:
    """État de session vivante : données seules, jamais une autorisation."""

    id: str = ""
    state: str = "NEW"
    dialogue: DialogueState = DialogueState()
    pending: Optional[PendingDemand] = None
    turn_counter: int = 0
    reason: str = ""


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) \
        and len(value) <= 128


def open_session(session_id: Any) -> Tuple[bool, Any]:
    """Crée une session NEW. Identifiant valide exigé, sans effet."""
    if not _valid_id(session_id):
        return False, "session-invalide"
    return True, LiveSession(id=session_id.strip(), state="NEW")


def _transition(live: LiveSession, target: str,
                reason: str = "") -> Tuple[bool, Any]:
    if not isinstance(live, LiveSession):
        return False, "session-invalide"
    if target not in _LIVE_TRANSITIONS.get(live.state, ()):
        return False, "transition-invalide"
    return True, LiveSession(id=live.id, state=target,
                             dialogue=live.dialogue, pending=live.pending,
                             turn_counter=live.turn_counter, reason=reason)


def _memory_turns(memory: Any, session_id: str,
                  limit: int = MAX_MEMORY_TURNS) -> List[Dict[str, Any]]:
    if memory is None:
        return []
    try:
        recalled = recall_context(memory, session_id=session_id,
                                  limit=limit)
    except Exception:
        return []
    turns = []
    for turn in recalled if isinstance(recalled, list) else []:
        if isinstance(turn, dict) and isinstance(turn.get("text"), str) \
                and turn["text"].strip():
            turns.append({"role": "wilfrid-memory",
                          "text": turn["text"].strip(),
                          "record_id": str(turn.get("record_id", "")),
                          "freshness": str(turn.get("freshness", "UNKNOWN")),
                          "provenance": str(turn.get("provenance", ""))})
    return turns


def submit_turn(live: Any, gate: Any, text: Any, *, now: Any,
                source: str = "text", search_fn: Any = None,
                memory: Any = None, memorize: bool = False,
                router_fn: Any = None, mandates: Any = None,
                journal: Any = None, payload: Any = None,
                catalog: Any = None,
                skill_id: str = "wilfrid-core",
                skill_version: str = "1.0",
                expires_at: Any = None,
                session_id: Any = None) -> Tuple[Any, LoopResult]:
    """Un tour dans une session vivante. États fermés, zéro effet direct."""
    if not isinstance(live, LiveSession):
        return live, LoopResult(kind="ERROR", detail="session-invalide")
    if session_id is not None and session_id != live.id:
        return live, LoopResult(kind="ERROR", detail="session-incoherente")
    if live.state in ("CLOSED", "ERROR"):
        return live, LoopResult(kind="ERROR", detail="session-terminee")
    if live.state == "PAUSED":
        return live, LoopResult(kind="ERROR", detail="session-en-pause")
    if live.state == "WAITING_CONFIRMATION":
        return live, LoopResult(kind="ERROR", detail="confirmation-en-attente")
    if live.state not in ("NEW", "ACTIVE"):
        return live, LoopResult(kind="ERROR", detail="etat-inattendu")
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        return live, LoopResult(kind="ERROR", detail="texte-invalide")
    working = DialogueState(history=live.dialogue.history
                            + tuple(_memory_turns(memory, live.id)),
                            pending=None,
                            turn_index=live.dialogue.turn_index)
    try:
        new_dialogue, result = run_text_turn(
            working, gate, text, session_id=live.id, now=now, source=source,
            search_fn=search_fn, memory=memory, memorize=memorize,
            skill_id=skill_id, skill_version=skill_version,
            expires_at=expires_at, router_fn=router_fn, mandates=mandates,
            journal=journal, payload=payload, catalog=catalog)
    except Exception:
        errored = LiveSession(id=live.id, state="ERROR",
                              dialogue=live.dialogue, pending=None,
                              turn_counter=live.turn_counter,
                              reason="erreur-tour")
        return errored, LoopResult(kind="ERROR", detail="erreur-tour")
    counter = live.turn_counter + 1
    if result.kind == "CONFIRM_CREATED":
        pending: Optional[PendingDemand] = None
        if result.request is not None:
            request = result.request
            pending = PendingDemand(
                confirmation_id=result.confirmation_id,
                request_id=str(getattr(request, "request_id", "")),
                permission_id=str(getattr(request, "permission_id", "")),
                scope=str(getattr(request, "scope", "")),
                target=str(getattr(request, "target", "")),
                limits=tuple(sorted(
                    (str(key), str(value))
                    for key, value in (
                        request.limits.items()
                        if isinstance(request.limits, dict) else []))),
                duration_s=request.duration_s
                if isinstance(getattr(request, "duration_s", 0), int)
                and not isinstance(getattr(request, "duration_s", 0),
                                   bool) else 0,
                reason="tour")
        waiting = LiveSession(id=live.id, state="WAITING_CONFIRMATION",
                              dialogue=new_dialogue, pending=pending,
                              turn_counter=counter,
                              reason="confirmation-en-attente")
        return waiting, result
    active = LiveSession(id=live.id, state="ACTIVE", dialogue=new_dialogue,
                         pending=None, turn_counter=counter, reason="tour")
    if live.state == "NEW":
        ok, active = _transition(
            LiveSession(id=live.id, state="NEW", dialogue=new_dialogue,
                        pending=None, turn_counter=counter, reason="tour"),
            "ACTIVE", reason="tour")
        if not ok:
            return live, LoopResult(kind="ERROR", detail="transition-impossible")
    return active, result


def resolve_live(gate: Any, live: Any, decision: Any, decided_by: Any, *,
                 now: Any, journal: Any = None, payload: Any = None,
                 catalog: Any = None, memory: Any = None,
                 memorize: bool = False) -> Tuple[Any, LoopResult]:
    """Résout la confirmation en attente, puis revient à ACTIVE ou échoue proprement."""
    if not isinstance(live, LiveSession):
        return live, LoopResult(kind="ERROR", detail="session-invalide")
    if live.state != "WAITING_CONFIRMATION" or live.pending is None:
        return live, LoopResult(kind="ERROR", detail="rien-en-attente")
    if decision not in ("APPROVE", "DENY"):
        return live, LoopResult(kind="ERROR", detail="decision-invalide")
    if not isinstance(gate, ApprovalGate):
        return live, LoopResult(kind="ERROR", detail="gate-invalide")
    pending = live.pending
    stored = gate.get(pending.confirmation_id)
    if stored is None or getattr(stored, "state", "") in (
            "CONSUMED", "EXPIRED", "DENIED"):
        cleared = LiveSession(id=live.id, state="ACTIVE",
                              dialogue=live.dialogue, pending=None,
                              turn_counter=live.turn_counter,
                              reason="attente-invalidee")
        return cleared, LoopResult(kind="ERROR", detail="confirmation-invalide")
    from core.p7.types import Request
    limits: Dict[str, Any] = {}
    for key, value in pending.limits:
        try:
            limits[str(key)] = int(str(value)) \
                if str(value).lstrip("-").isdigit() else str(value)
        except (TypeError, ValueError):
            limits[str(key)] = str(value)
    request = Request(
        request_id=pending.request_id, skill_id="wilfrid-core",
        skill_version="1.0", permission_id=pending.permission_id,
        scope=pending.scope, target=pending.target,
        limits=limits, duration_s=pending.duration_s,
        reason="reprise-session")
    result = resolve_confirmation(
        gate, pending.confirmation_id, decision, decided_by, request=request,
        session_id=live.id, turn_index=live.turn_counter, now=now,
        journal=journal, payload=payload, catalog=catalog, memory=memory,
        memorize=memorize)
    if result.kind == "CONFIRM_RESOLVED":
        cleared = LiveSession(id=live.id, state="ACTIVE",
                              dialogue=live.dialogue, pending=None,
                              turn_counter=live.turn_counter,
                              reason="confirmation-resolue")
        return cleared, result
    if result.kind == "REFUSED":
        cleared = LiveSession(id=live.id, state="ACTIVE",
                              dialogue=live.dialogue, pending=None,
                              turn_counter=live.turn_counter,
                              reason="confirmation-refusee")
        return cleared, result
    return live, result


def pause_live(live: Any) -> Tuple[bool, Any]:
    """Suspend les nouveaux tours. Conserve tout, n'autorise rien."""
    if not isinstance(live, LiveSession):
        return False, "session-invalide"
    return _transition(live, "PAUSED", reason="pause")


def resume_live(live: Any) -> Tuple[bool, Any]:
    """Reprend : PAUSED → ACTIVE (ou WAITING si une demande subsiste)."""
    if not isinstance(live, LiveSession):
        return False, "session-invalide"
    if live.state != "PAUSED":
        return False, "transition-invalide"
    target = "WAITING_CONFIRMATION" if live.pending is not None else "ACTIVE"
    if target == "WAITING_CONFIRMATION":
        resumed = LiveSession(id=live.id, state="WAITING_CONFIRMATION",
                              dialogue=live.dialogue, pending=live.pending,
                              turn_counter=live.turn_counter,
                              reason="reprise-attente")
        return True, resumed
    return _transition(live, "ACTIVE", reason="reprise")


def close_live(live: Any) -> Tuple[bool, Any]:
    """Ferme : terminal. Aucun nouveau tour, lecture seule d'état."""
    if not isinstance(live, LiveSession):
        return False, "session-invalide"
    if live.state == "CLOSED":
        return True, live
    return _transition(live, "CLOSED", reason="fermeture")


def describe(live: Any) -> Dict[str, Any]:
    """État consultable : identifiant, état, compteur, attente (sans secret)."""
    if not isinstance(live, LiveSession):
        return {"state": "invalide"}
    pending = live.pending
    return {
        "id": live.id,
        "state": live.state,
        "turn_counter": live.turn_counter,
        "history_turns": len(live.dialogue.history),
        "pending_confirmation": pending.confirmation_id
        if pending is not None else "",
        "reason": live.reason,
    }
