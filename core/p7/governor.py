"""Wilfrid — gouverneur P7 C1 (décision pure, sans effet).

Séquence : typing → approval → scope → expiry → limits → journal-disponible.
C1 n'exécute aucune capacité : ALLOW = feux tous verts sur pièces fournies,
aucune touche FS/réseau, aucun effet. Toute erreur/ambiguïté = DENY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.p7 import errors as E
from core.p7.types import (
    B2_IDS,
    MAX_DURATION_S,
    RISK_OF,
    Approval,
    Proof,
    Request,
    target_in_scope,
    validate_limits,
    validate_scope_format,
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    proof: Proof


def _valid_request(req: Any) -> Tuple[bool, str]:
    if not isinstance(req, Request):
        return False, E.REQUEST_INVALID
    for attr in ("request_id", "skill_id", "skill_version", "permission_id",
                 "scope", "target", "reason"):
        value = getattr(req, attr, "")
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            return False, E.REQUEST_INVALID
    if req.permission_id not in B2_IDS:
        return False, E.PERMISSION_UNKNOWN
    if not isinstance(req.limits, dict):
        return False, E.REQUEST_INVALID
    ceiling = MAX_DURATION_S.get(req.permission_id, 0)
    if not isinstance(req.duration_s, int) or isinstance(req.duration_s, bool):
        return False, E.REQUEST_INVALID
    if req.duration_s <= 0 or req.duration_s > ceiling:
        return False, E.LIMITS_INVALID
    return True, "ok"


def decide(request: Request, approval: Optional[Approval],
           now: float, journal_available: bool) -> Decision:
    """Décide ALLOW/DENY sans effet. `now` = horloge monotonic injectée."""
    try:
        ok, why = _valid_request(request)
        if not ok:
            return Decision(False, why, Proof(request.request_id
                                              if isinstance(request, Request) else "",
                                              getattr(request, "permission_id", "")
                                              if isinstance(request, Request) else "",
                                              "DENY", why, 0, ("typing",)))
        if not isinstance(approval, Approval):
            return Decision(False, E.APPROVAL_ABSENT,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_ABSENT, 0, ("approval",)))
        if approval.request_id != request.request_id:
            return Decision(False, E.APPROVAL_ABSENT,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_ABSENT, 0, ("approval",)))
        if approval.permission_id != request.permission_id:
            return Decision(False, E.APPROVAL_ABSENT,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_ABSENT, 0, ("approval",)))
        if str(approval.decision) != "accorde":
            return Decision(False, E.APPROVAL_ABSENT,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_ABSENT, 0, ("approval",)))
        if approval.revoked:
            return Decision(False, E.CAPABILITY_REVOKED,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.CAPABILITY_REVOKED,
                                  approval.capability_version, ("revocation",)))
        if approval.suspended:
            return Decision(False, E.CAPABILITY_SUSPENDED,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.CAPABILITY_SUSPENDED,
                                  approval.capability_version, ("suspension",)))
        try:
            expiry = float(approval.timestamp) + float(approval.duration_s)
            moment = float(now)
        except (TypeError, ValueError):
            return Decision(False, E.APPROVAL_EXPIRED,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_EXPIRED,
                                  approval.capability_version, ("expiry",)))
        if not (moment >= 0) or moment > expiry:
            return Decision(False, E.APPROVAL_EXPIRED,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.APPROVAL_EXPIRED,
                                  approval.capability_version, ("expiry",)))
        ok, why = validate_scope_format(request.scope)
        if not ok:
            return Decision(False, E.SCOPE_INVALID,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.SCOPE_INVALID,
                                  approval.capability_version, ("scope",)))
        if str(approval.scope) != str(request.scope):
            return Decision(False, E.SCOPE_NOT_COVERING,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.SCOPE_NOT_COVERING,
                                  approval.capability_version, ("scope",)))
        covered, _ = target_in_scope(request.scope, request.target)
        if not covered:
            return Decision(False, E.SCOPE_NOT_COVERING,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.SCOPE_NOT_COVERING,
                                  approval.capability_version, ("scope",)))
        ok, _ = validate_limits(request.permission_id, request.limits)
        if not ok:
            return Decision(False, E.LIMITS_INVALID,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.LIMITS_INVALID,
                                  approval.capability_version, ("limits",)))
        if journal_available is not True:
            return Decision(False, E.JOURNAL_UNAVAILABLE,
                            Proof(request.request_id, request.permission_id,
                                  "DENY", E.JOURNAL_UNAVAILABLE,
                                  approval.capability_version, ("journal",)))
        risk = RISK_OF.get(request.permission_id, "")
        return Decision(True, "ok", Proof(request.request_id,
                                          request.permission_id, "ALLOW", "ok",
                                          approval.capability_version,
                                          ("typing", "approval", "scope",
                                           "expiry", "limits", "journal")))
    except Exception:
        rid = getattr(request, "request_id", "") if isinstance(request, Request) else ""
        pid = getattr(request, "permission_id", "") if isinstance(request, Request) else ""
        return Decision(False, E.UNKNOWN_ERROR, Proof(rid, pid, "DENY",
                                                      E.UNKNOWN_ERROR, 0, ()))


def journal_gate(journal_available: bool) -> Tuple[bool, str]:
    """Garde-fous journal : indisponible = DENY TOTAL (sans lever)."""
    if journal_available is not True:
        return False, E.JOURNAL_UNAVAILABLE
    return True, "ok"
