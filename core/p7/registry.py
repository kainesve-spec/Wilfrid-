"""Wilfrid — registre P7 C1 (deny-by-default, non activable).

Structure technique vide par défaut. Aucune méthode d'activation :
ni enable, ni grant, ni accord implicite. `declare` ajoute une fiche
disabled ; `revoke`/`suspend` ne font que marquer (toujours DENY au check).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.p7 import errors as E
from core.p7.types import B2_IDS, PermissionRecord


class Registry:
    """Registre vide par défaut, refus de tout absent."""

    def __init__(self) -> None:
        self._permissions: Dict[str, PermissionRecord] = {}

    def declare(self, permission_id: str, scope: str = "",
                limits: Dict[str, Any] | None = None,
                reason: str = "declared-disabled") -> PermissionRecord:
        if permission_id not in B2_IDS:
            raise ValueError(f"permission inconnue: {permission_id}")
        rec = PermissionRecord(
            id=permission_id,
            enabled=False,
            scope=str(scope or ""),
            limits=dict(limits or {}),
            version=1,
            reason=str(reason or "declared-disabled"),
        )
        self._permissions[permission_id] = rec
        return rec

    def revoke(self, permission_id: str, reason: str = "revoked") -> PermissionRecord:
        current = self._permissions.get(permission_id)
        if current is None:
            raise ValueError(f"permission inconnue: {permission_id}")
        rec = PermissionRecord(
            id=current.id,
            enabled=False,
            scope=current.scope,
            limits=dict(current.limits),
            version=current.version + 1,
            reason=str(reason),
            revoked=True,
            suspended=current.suspended,
        )
        self._permissions[permission_id] = rec
        return rec

    def suspend(self, permission_id: str, reason: str = "suspended") -> PermissionRecord:
        current = self._permissions.get(permission_id)
        if current is None:
            raise ValueError(f"permission inconnue: {permission_id}")
        rec = PermissionRecord(
            id=current.id,
            enabled=False,
            scope=current.scope,
            limits=dict(current.limits),
            version=current.version + 1,
            reason=str(reason),
            revoked=current.revoked,
            suspended=True,
        )
        self._permissions[permission_id] = rec
        return rec

    def check(self, permission_id: str, target: str = "") -> Tuple[bool, str]:
        rec = self._permissions.get(str(permission_id))
        if rec is None:
            return False, E.PERMISSION_UNKNOWN
        if rec.revoked:
            return False, E.CAPABILITY_REVOKED
        if rec.suspended:
            return False, E.CAPABILITY_SUSPENDED
        return False, E.PERMISSION_DISABLED

    def active_count(self) -> int:
        return sum(1 for r in self._permissions.values() if r.enabled)

    def is_empty(self) -> bool:
        return len(self._permissions) == 0

    def status(self) -> List[Dict[str, Any]]:
        return [{"id": r.id, "enabled": r.enabled, "scope": r.scope,
                 "limits": dict(r.limits), "version": r.version,
                 "reason": r.reason, "revoked": r.revoked,
                 "suspended": r.suspended}
                for r in self._permissions.values()]
