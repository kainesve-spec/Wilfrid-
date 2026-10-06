"""Wilfrid — notification locale P7.NOTIFY_LOCAL (R2, strictement locale).

Canal unique `~/Wilfrid/JAIL/P7/notifications/`, créé uniquement par ce module
(C3). Texte seul ≤280 caractères, 1/request, timeout 1–3 s, durée ≤5 min,
single-use en mémoire. Contenus interdits : secrets/credentials, URLs réseau,
métacaractères shell (fail-closed conservateur), multiligne. Le texte n'est
jamais interprété ni exécuté : octets inertes uniquement. Aucun réseau,
aucune destination externe, aucune pièce jointe, aucune écriture hors canal.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import resolver as R
from core.p7.journal import Journal
from core.p7.types import Approval, Request

PERMISSION_ID = "P7.NOTIFY_LOCAL"
CHANNEL_DIRNAME = "notifications"
MAX_CHARS = 280
FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}\.json$")
_SECRET_HINTS = ("secret", "credential", "passwd", "api_key", "apikey",
                 "bearer", "-----begin", ".env")
_NETWORK_HINTS = ("http://", "https://", "://", "socket")
_SHELL_HINTS = ("$(", "`", "&&", "||", ";", "\n", "\r")

_CONSUMED: set = set()


def reset_consumed() -> None:
    _CONSUMED.clear()


def channel_dir() -> Path:
    return R.jail_root() / CHANNEL_DIRNAME


def ensure_channel() -> Tuple[bool, str, Optional[Path]]:
    """Crée le canal local (C3 uniquement), 0o700, jamais un symlink."""
    directory = channel_dir()
    try:
        if directory.is_symlink():
            return False, E.SCOPE_NOT_COVERING, None
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not directory.is_dir() or directory.is_symlink():
            return False, E.SCOPE_NOT_COVERING, None
    except OSError as exc:
        return False, f"{E.UNKNOWN_ERROR}:{type(exc).__name__}", None
    return True, "ok", directory


def _deny(reason: str, request: Request,
          approval: Optional[Approval]) -> Tuple[G.Decision, None]:
    version = approval.capability_version if isinstance(approval, Approval) else 0
    rid = request.request_id if isinstance(request, Request) else ""
    pid = request.permission_id if isinstance(request, Request) else ""
    return G.Decision(False, reason, G.Proof(rid, pid, "DENY", reason, version,
                                             ("notify",))), None


def _note(journal: Journal, event: str, request: Request,
          approval: Optional[Approval], decision: str, reason: str) -> bool:
    try:
        journal.record(event=event, actor="core",
                       request_id=request.request_id,
                       permission_id=request.permission_id,
                       target=request.target, decision=decision,
                       reason=reason,
                       capability_version=approval.capability_version
                       if isinstance(approval, Approval) else 0,
                       risk="R2")
    except Exception:
        return False
    return True


def _content_ok(text: Any) -> Tuple[bool, str]:
    if not isinstance(text, str):
        return False, "PIÈCE_JOINTE_OU_NON_TEXTE"
    if not text or len(text) > MAX_CHARS:
        return False, E.LIMITS_INVALID
    lowered = text.lower()
    if any(h in lowered for h in _SECRET_HINTS):
        return False, "CONTENU_INTERDIT"
    if any(h in lowered for h in _NETWORK_HINTS):
        return False, "CONTENU_INTERDIT"
    if any(h in text for h in _SHELL_HINTS):
        return False, "CONTENU_INTERDIT"
    return True, "ok"


def expected_target(request_id: str) -> str:
    return f"{channel_dir()}/{request_id}.json"


def notify(request: Request, approval: Optional[Approval],
           now: float, journal: Journal, text: str) -> Tuple[G.Decision, Optional[Dict[str, Any]]]:
    """Émet 1 notification texte bornée vers le canal. Single-use."""
    t0 = time.monotonic()
    decision = G.decide(request, approval, now, journal.available())
    if not decision.allowed:
        return decision, None
    if request.permission_id != PERMISSION_ID:
        return _deny(E.PERMISSION_UNKNOWN, request, approval)
    if request.request_id in _CONSUMED:
        return _deny("SECONDE_ACTION", request, approval)
    if FILENAME_RE.match(f"{request.request_id}.json") is None:
        return _deny(E.REQUEST_INVALID, request, approval)
    timeout_s = request.limits.get("timeout_s", 0)
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool):
        return _deny(E.LIMITS_INVALID, request, approval)
    if timeout_s < 1 or timeout_s > 3:
        return _deny(E.LIMITS_INVALID, request, approval)
    if request.limits.get("per_request", 1) != 1:
        return _deny(E.LIMITS_INVALID, request, approval)
    if str(request.scope) != f"notification:{request.target}:textuel-borné":
        return _deny(E.SCOPE_NOT_COVERING, request, approval)
    if str(request.target) != expected_target(request.request_id):
        return _deny(E.SCOPE_NOT_COVERING, request, approval)
    ok_c, why_c, directory = ensure_channel()
    if not ok_c or directory is None:
        return _deny(why_c, request, approval)
    ok_r, why_r, confined = R.resolve(request.scope, request.target)
    if not ok_r or confined is None:
        return _deny(why_r, request, approval)
    try:
        if confined.parent.resolve() != directory.resolve():
            return _deny(E.SCOPE_NOT_COVERING, request, approval)
    except OSError:
        return _deny(E.SCOPE_NOT_COVERING, request, approval)
    good, why_content = _content_ok(text)
    if not good:
        return _deny(why_content, request, approval)
    if not journal.available():
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    if not _note(journal, "pre-notify", request, approval, "ALLOW", "ok"):
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    try:
        ok_r2, _, confined2 = R.resolve(request.scope, request.target)
        if not ok_r2 or confined2 is None or confined2 != confined:
            raise OSError("target-changed")
        if confined2.is_symlink():
            raise OSError("target-symlink")
        if confined2.exists():
            raise OSError("already-notified")
        tmp = confined2.parent / f".tmp.{request.request_id}"
        if tmp.is_symlink():
            raise OSError("tmp-symlink")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(confined2)
    except OSError as exc:
        _note(journal, "error", request, approval, "DENY",
              f"NOTIFY_FAIL:{type(exc).__name__}")
        return _deny(f"NOTIFY_FAIL:{type(exc).__name__}", request, approval)
    try:
        observed = confined.read_text(encoding="utf-8")
        if observed != text:
            raise OSError("post-mismatch")
    except OSError:
        _note(journal, "error", request, approval, "DENY", "POST_FAIL")
        return _deny("POST_FAIL", request, approval)
    if time.monotonic() - t0 > timeout_s:
        return _deny(E.LIMITS_INVALID, request, approval)
    _CONSUMED.add(request.request_id)
    _note(journal, "post-notify", request, approval, "ALLOW", "ok")
    return decision, {"target": str(confined), "chars": len(text)}


def describe() -> Dict[str, Any]:
    return {"id": PERMISSION_ID, "risk": "R2", "channel": str(channel_dir()),
            "max_chars": MAX_CHARS, "per_request": 1, "timeout_s": 3,
            "duration_s": 300, "single_use": True}
