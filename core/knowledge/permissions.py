"""Wilfrid — permissions P6.1 (refus par défaut, activation explicite).

Aucune permission ne peut être activée par le contenu d'un document :
seuls des appels explicites `enable()`/`revoke()` changent l'état.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

PERMISSION_IDS = (
    "INTERNET_RESEARCH",
    "SOURCE_ACCESS",
    "DOCUMENT_DOWNLOAD",
    "DOCUMENT_PERSIST",
    "KNOWLEDGE_WRITE",
    "KNOWLEDGE_UPDATE",
    "CROSS_DOCUMENT_ANALYSIS",
    "NOTIFY_COMPLETION",
)

LogCallback = Optional[Callable[..., None]]


@dataclass
class Permission:
    """Permission versionnée, désactivée par défaut, révocable."""

    id: str
    enabled: bool = False
    scope: str = ""
    limits: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    reason: str = "default-deny"


class PermissionRegistry:
    """Registre : tout accès externe est refusé sauf activation explicite."""

    def __init__(self, log_callback: LogCallback = None):
        self._permissions: Dict[str, Permission] = {
            pid: Permission(id=pid) for pid in PERMISSION_IDS
        }
        self._log = log_callback

    def _record(self, action: str, permission_id: str, decision: str,
                reason: str, target: str = "") -> None:
        if self._log is not None:
            self._log(action=action, permission_id=permission_id,
                      decision=decision, reason=reason, target=target)

    def enable(self, permission_id: str, scope: str = "",
               limits: Optional[Dict[str, Any]] = None,
               reason: str = "explicit") -> Permission:
        perm = self._get(permission_id)
        perm.enabled = True
        perm.scope = scope
        perm.limits = dict(limits or {})
        perm.version += 1
        perm.reason = reason
        self._record("permission.enable", permission_id, "ALLOW", reason)
        return perm

    def revoke(self, permission_id: str, reason: str = "revoked") -> Permission:
        perm = self._get(permission_id)
        perm.enabled = False
        perm.version += 1
        perm.reason = reason
        self._record("permission.revoke", permission_id, "DENY", reason)
        return perm

    def check(self, permission_id: str, target: str = "") -> Tuple[bool, str]:
        perm = self._permissions.get(permission_id)
        if perm is None:
            reason = "unknown-permission"
            self._record("permission.check", permission_id, "DENY", reason,
                         target)
            return False, reason
        if not perm.enabled:
            reason = "disabled"
            self._record("permission.check", permission_id, "DENY", reason,
                         target)
            return False, reason
        self._record("permission.check", permission_id, "ALLOW", perm.reason,
                     target)
        return True, perm.reason

    def status(self) -> List[Dict[str, Any]]:
        return [{"id": p.id, "enabled": p.enabled, "scope": p.scope,
                 "limits": dict(p.limits), "version": p.version,
                 "reason": p.reason}
                for p in self._permissions.values()]

    def _get(self, permission_id: str) -> Permission:
        try:
            return self._permissions[permission_id]
        except KeyError:
            raise ValueError(f"permission inconnue: {permission_id}")
