"""Wilfrid — fondations P7.1 / C1 (contrats inertes, sans effet).

Vocabulaire gelé P7.0-A. Les 4 IDs B2 sont des constantes déclaratives :
aucune activation, aucun effet, aucun accès fichier/réseau ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

B2_IDS = (
    "P7.CATALOG_READ",
    "P7.JAIL_READ",
    "P7.JAIL_WRITE_REVERSIBLE",
    "P7.NOTIFY_LOCAL",
)

RISK_OF = {
    "P7.CATALOG_READ": "R0",
    "P7.JAIL_READ": "R1",
    "P7.JAIL_WRITE_REVERSIBLE": "R2",
    "P7.NOTIFY_LOCAL": "R2",
}

MAX_LIMITS = {
    "P7.CATALOG_READ": {"entries": 50, "bytes": 8192},
    "P7.JAIL_READ": {"files": 5, "total_bytes": 262144, "file_bytes": 65536,
                     "depth": 3, "timeout_s": 5},
    "P7.JAIL_WRITE_REVERSIBLE": {"files": 1, "file_bytes": 65536, "timeout_s": 5},
    "P7.NOTIFY_LOCAL": {"chars": 280, "per_request": 1, "timeout_s": 3},
}

MAX_DURATION_S = {
    "P7.CATALOG_READ": 3600,
    "P7.JAIL_READ": 600,
    "P7.JAIL_WRITE_REVERSIBLE": 300,
    "P7.NOTIFY_LOCAL": 300,
}

_BANNED_SCOPE_SUBSTRINGS = ("*", "..", "\n", "\r", "\x00")


def _clean(text: Any) -> str:
    return str(text or "")


def validate_scope_format(scope: Any) -> Tuple[bool, str]:
    s = _clean(scope)
    if not s or len(s) > 512:
        return False, "empty-or-oversize"
    parts = s.split(":")
    if len(parts) != 3 or not all(p.strip() for p in parts):
        return False, "malformed-triplet"
    if any(b in s for b in _BANNED_SCOPE_SUBSTRINGS):
        return False, "banned-pattern"
    resource = parts[0].strip()
    if resource not in ("catalogue", "fichier", "notification"):
        return False, "unknown-resource"
    return True, "ok"


def target_in_scope(scope: Any, target: Any) -> Tuple[bool, str]:
    ok, why = validate_scope_format(scope)
    if not ok:
        return False, why
    t = _clean(target)
    if not t or len(t) > 512:
        return False, "empty-target"
    if any(b in t for b in _BANNED_SCOPE_SUBSTRINGS):
        return False, "banned-target"
    perimeter = str(scope).split(":")[1].strip()
    if t != perimeter:
        return False, "not-covering"
    return True, "ok"


def validate_limits(permission_id: Any, limits: Any) -> Tuple[bool, str]:
    pid = _clean(permission_id)
    if pid not in MAX_LIMITS:
        return False, "unknown-permission"
    if not isinstance(limits, dict):
        return False, "limits-not-dict"
    caps = MAX_LIMITS[pid]
    for key, ceiling in caps.items():
        value = limits.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool):
            return False, f"limits-bad-type:{key}"
        if value < 0 or value > ceiling:
            return False, f"limits-exceeded:{key}"
    return True, "ok"


@dataclass(frozen=True)
class PermissionRecord:
    """Fiche permission C1 : naissance disabled, sans activation possible ici."""

    id: str = ""
    enabled: bool = False
    scope: str = ""
    limits: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    reason: str = "declared-disabled"
    revoked: bool = False
    suspended: bool = False


@dataclass(frozen=True)
class Request:
    """Demande typée C1 : 1 périmètre + 1 cible, données seules."""

    request_id: str = ""
    skill_id: str = ""
    skill_version: str = ""
    permission_id: str = ""
    scope: str = ""
    target: str = ""
    limits: Dict[str, Any] = field(default_factory=dict)
    duration_s: int = 0
    reason: str = ""


@dataclass(frozen=True)
class Approval:
    """Approbation C1 : données seules, silence = refus (absence d'objet)."""

    request_id: str = ""
    permission_id: str = ""
    decision: str = "refuse"
    scope: str = ""
    duration_s: int = 0
    reason: str = ""
    capability_version: int = 1
    timestamp: float = 0.0
    revoked: bool = False
    suspended: bool = False


@dataclass(frozen=True)
class Proof:
    """Preuve minimale C1 : corrélation sans effet exécuté."""

    request_id: str = ""
    permission_id: str = ""
    decision: str = ""
    reason: str = ""
    capability_version: int = 0
    checks: Tuple[str, ...] = ()
