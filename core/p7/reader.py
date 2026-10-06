"""Wilfrid — lecture bornée P7.JAIL_READ (R1, sans effet de bord).

Flux : typing→approval→scope→expiry→limits→résolution→journal pre-event→
lecture→vérification→preuve→journal post-event. Aucun open avant verdict,
aucun réseau, aucun write. Batch `read_many` : ≤5 fichiers, ≤256 Ko total,
tout-ou-rien (octets déjà lus écartés si DENY global).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import resolver as R
from core.p7.journal import Journal
from core.p7.types import Approval, MAX_LIMITS, Request

PERMISSION_ID = "P7.JAIL_READ"
MAX_FILES = 5
MAX_TOTAL_BYTES = 262144
MAX_FILE_BYTES = 65536


def _deny(reason: str, request: Request,
          approval: Optional[Approval]) -> Tuple[G.Decision, None]:
    version = approval.capability_version if isinstance(approval, Approval) else 0
    return G.Decision(False, reason, G.Proof(
        request.request_id if isinstance(request, Request) else "",
        request.permission_id if isinstance(request, Request) else "",
        "DENY", reason, version, ("reader",))), None


def _journal_note(journal: Journal, event: str, request: Request,
                  approval: Optional[Approval], decision: str,
                  reason: str) -> bool:
    try:
        journal.record(event=event, actor="core",
                       request_id=request.request_id,
                       permission_id=request.permission_id,
                       target=request.target, decision=decision,
                       reason=reason,
                       capability_version=approval.capability_version
                       if isinstance(approval, Approval) else 0,
                       risk="R1")
    except Exception:
        return False
    return True


def read_one(request: Request, approval: Optional[Approval],
             now: float, journal: Journal) -> Tuple[G.Decision, Optional[bytes]]:
    """Lit 1 fichier exact confiné. DENY + zéro effet à tout échec."""
    t0 = time.monotonic()
    available = journal.available()
    decision = G.decide(request, approval, now, available)
    if not decision.allowed:
        return decision, None
    if request.permission_id != PERMISSION_ID:
        return _deny(E.PERMISSION_UNKNOWN, request, approval)
    file_bytes = request.limits.get("file_bytes", 0)
    timeout_s = request.limits.get("timeout_s", 0)
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool):
        return _deny(E.LIMITS_INVALID, request, approval)
    if timeout_s < 1 or timeout_s > 5:
        return _deny(E.LIMITS_INVALID, request, approval)
    if not isinstance(file_bytes, int) or isinstance(file_bytes, bool):
        return _deny(E.LIMITS_INVALID, request, approval)
    if file_bytes < 0 or file_bytes > MAX_FILE_BYTES:
        return _deny(E.LIMITS_INVALID, request, approval)
    ok, why, path = R.resolve(request.scope, request.target)
    if not ok or path is None:
        return _deny(why, request, approval)
    if not journal.available():
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    if not _journal_note(journal, "pre-read", request, approval, "ALLOW", "ok"):
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    try:
        ok2, _, path2 = R.resolve(request.scope, request.target)
        if not ok2 or path2 is None or path2 != path:
            _journal_note(journal, "error", request, approval, "DENY", why)
            return _deny(E.SCOPE_NOT_COVERING, request, approval)
        if not path.is_file() or path.is_symlink():
            _journal_note(journal, "error", request, approval,
                          "DENY", "CIBLE_INEXISTANTE")
            return _deny("CIBLE_INEXISTANTE", request, approval)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES or size > file_bytes:
            _journal_note(journal, "error", request, approval,
                          "DENY", E.LIMITS_INVALID)
            return _deny(E.LIMITS_INVALID, request, approval)
        data = path.read_bytes()
    except OSError as exc:
        _journal_note(journal, "error", request, approval, "DENY",
                      f"{E.UNKNOWN_ERROR}:{type(exc).__name__}")
        return _deny(E.UNKNOWN_ERROR, request, approval)
    if time.monotonic() - t0 > timeout_s:
        return _deny(E.LIMITS_INVALID, request, approval)
    try:
        if path.is_symlink() or not path.is_file():
            return _deny(E.SCOPE_NOT_COVERING, request, approval)
        if len(data) > MAX_FILE_BYTES or len(data) > file_bytes:
            return _deny(E.LIMITS_INVALID, request, approval)
    except OSError:
        return _deny(E.UNKNOWN_ERROR, request, approval)
    _journal_note(journal, "post-read", request, approval, "ALLOW", "ok")
    return decision, data


def read_many(pairs: List[Tuple[Request, Optional[Approval]]],
              now: float, journal: Journal) -> Tuple[G.Decision, Optional[List[bytes]]]:
    """Batch borné tout-ou-rien : >5 requêtes = DENY sans toucher FS."""
    if not isinstance(pairs, list) or len(pairs) == 0 or len(pairs) > MAX_FILES:
        empty = pairs[0][0] if isinstance(pairs, list) and pairs else None
        reason = E.LIMITS_INVALID
        if isinstance(empty, Request):
            return G.Decision(False, reason, G.Proof(
                empty.request_id, empty.permission_id, "DENY", reason, 0,
                ("reader-batch",))), None
        return G.Decision(False, reason, G.Proof(
            "", "", "DENY", reason, 0, ("reader-batch",))), None
    collected: List[bytes] = []
    total = 0
    for request, approval in pairs:
        decision, data = read_one(request, approval, now, journal)
        if not decision.allowed or data is None:
            return decision, None
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            deny = G.Decision(False, E.LIMITS_INVALID, G.Proof(
                request.request_id, request.permission_id, "DENY",
                E.LIMITS_INVALID,
                approval.capability_version if isinstance(approval, Approval) else 0,
                ("reader-batch",)))
            return deny, None
        collected.append(data)
    first = pairs[0][0]
    ok = G.Decision(True, "ok", G.Proof(
        first.request_id, first.permission_id, "ALLOW", "ok", 0,
        ("reader-batch",)))
    return ok, collected


def describe() -> Dict[str, Any]:
    return {"id": PERMISSION_ID, "risk": "R1", "max_files": MAX_FILES,
            "max_total_bytes": MAX_TOTAL_BYTES, "max_file_bytes": MAX_FILE_BYTES,
            "max_depth": R.MAX_DEPTH, "timeout_s": 5, "duration_s": 600}
