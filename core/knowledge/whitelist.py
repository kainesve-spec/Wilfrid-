"""Wilfrid — whitelist P6.1 (vide par défaut, ajouts explicites seuls).

Modèle HTTPS uniquement. Source absente = refus explicite journalisé.
Le contenu d'un document ne peut ni ajouter ni modifier la whitelist :
seuls `add()`/`revoke()` le peuvent.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

LogCallback = Optional[Callable[..., None]]


@dataclass
class WhitelistEntry:
    domain: str
    https_only: bool = True
    version: int = 1
    status: str = "active"
    date: str = ""
    limits: Dict[str, Any] = field(default_factory=dict)


def _today_iso() -> str:
    return datetime.date.today().isoformat()


class Whitelist:
    """Liste de sources autorisées. Vide par défaut."""

    def __init__(self, log_callback: LogCallback = None):
        self._entries: Dict[str, WhitelistEntry] = {}
        self._log = log_callback

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        domain = (domain or "").strip().lower()
        if "://" in domain:
            domain = urlparse(domain).hostname or domain
        return domain.rstrip(".")

    def add(self, domain: str, limits: Optional[Dict[str, Any]] = None,
            reason: str = "explicit") -> WhitelistEntry:
        name = self._normalize_domain(domain)
        if not name or "." not in name:
            raise ValueError(f"domaine invalide: {domain!r}")
        entry = WhitelistEntry(domain=name, limits=dict(limits or {}),
                               date=_today_iso())
        self._entries[name] = entry
        if self._log is not None:
            self._log(action="whitelist.add", permission_id="SOURCE_ACCESS",
                      decision="ALLOW", reason=reason, target=name)
        return entry

    def revoke(self, domain: str, reason: str = "revoked") -> bool:
        name = self._normalize_domain(domain)
        entry = self._entries.get(name)
        if entry is None:
            return False
        entry.status = "revoked"
        if self._log is not None:
            self._log(action="whitelist.revoke", permission_id="SOURCE_ACCESS",
                      decision="DENY", reason=reason, target=name)
        return True

    def check_url(self, url: str) -> Tuple[bool, str]:
        """Source absente ou révoquée = refus explicite. Aucun accès réseau."""
        try:
            parts = urlparse(url)
        except Exception:
            return False, "url-invalide"
        if (parts.scheme or "").lower() != "https":
            self._deny(url, "protocole-non-https")
            return False, "protocole-non-https"
        name = self._normalize_domain(parts.hostname or "")
        entry = self._entries.get(name)
        if entry is None:
            self._deny(url, "source-absente-whitelist")
            return False, "source-absente-whitelist"
        if entry.status != "active":
            self._deny(url, "source-revoquee")
            return False, "source-revoquee"
        return True, "autorise"

    def _deny(self, target: str, reason: str) -> None:
        if self._log is not None:
            self._log(action="whitelist.check", permission_id="SOURCE_ACCESS",
                      decision="DENY", reason=reason, target=target)

    def entries(self) -> List[Dict[str, Any]]:
        return [{"domain": e.domain, "https_only": e.https_only,
                 "version": e.version, "status": e.status, "date": e.date,
                 "limits": dict(e.limits)}
                for e in self._entries.values()]
