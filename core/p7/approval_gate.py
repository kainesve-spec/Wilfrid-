"""Wilfrid — Approval Gate (verrou de validation humaine, sans exécution).

Enregistre des demandes PENDING et des décisions humaines explicites
(APPROVE/DENY), avec expiration, liaison cryptographique à la demande exacte
(empreinte immuable) et consommation atomique unique. Ne crée aucune
permission, n'exécute rien, ne lance ni subprocess ni réseau, ne touche ni au
Governor ni au registre : seule une décision humaine enregistrée ici peut
ensuite être consommée, une seule fois, pour la demande exacte approuvée.

Règles : PENDING n'exécute rien ; APPROVED ne vaut que pour la demande exacte
(empreinte) ; DENY/EXPIRED = zéro exécution ; CONSUMED irréversible (aucun
chemin CONSUMED → APPROVED) ; toute modification substantielle de la demande
invalide l'approbation ; aucune extension/mission/agent/mémoire ne peut
approuver (seul un `decided_by` humain explicite est enregistré, et un objet
étranger au gate n'est jamais reconnu).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

STATES = ("PENDING", "APPROVED", "DENIED", "EXPIRED", "CONSUMED")
TERMINAL_DENY = ("DENIED", "EXPIRED", "CONSUMED")


@dataclass(frozen=True)
class Confirmation:
    """Demande en attente : identité + empreinte de la demande exacte."""

    confirmation_id: str = ""
    request_id: str = ""
    permission_id: str = ""
    scope: str = ""
    target: str = ""
    fingerprint: str = ""
    context_hash: str = ""
    limits: Tuple[Tuple[str, str], ...] = ()
    expires_at: Optional[float] = None
    state: str = "PENDING"
    decided_by: str = ""
    decided_at: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class GateEvent:
    """Trace d'audit : séquence + événement + acteur, sans secret."""

    seq: int = 0
    event: str = ""
    confirmation_id: str = ""
    actor: str = ""
    timestamp: float = 0.0
    reason: str = ""


def _short(text: str, limit: int = 512) -> str:
    return text[:limit]


def demand_fingerprint(*, request_id: str = "", permission_id: str = "",
                       scope: str = "", target: str = "",
                       limits: Any = None,
                       context_hash: str = "") -> str:
    """Empreinte immuable d'une demande exacte (canonique, déterministe)."""
    items: List[str] = []
    if isinstance(limits, dict):
        items = [f"{key}={limits[key]}"
                 for key in sorted(limits, key=str)]
    elif isinstance(limits, (tuple, list)):
        items = [str(part) for part in limits]
    canonical = "|".join([str(request_id), str(permission_id), str(scope),
                          str(target), ",".join(items), str(context_hash)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ApprovalGate:
    """Registre de confirmations. Mémoire vive ; persistance à l'appelant."""

    def __init__(self) -> None:
        self._confirmations: Dict[str, Confirmation] = {}
        self._events: List[GateEvent] = []
        self._seq = 0

    def _log(self, event: str, confirmation_id: str, actor: str,
             timestamp: float, reason: str = "") -> None:
        self._seq += 1
        self._events.append(GateEvent(
            seq=self._seq, event=event,
            confirmation_id=_short(str(confirmation_id), 128),
            actor=_short(str(actor), 128),
            timestamp=float(timestamp), reason=_short(str(reason), 256)))

    def _valid_id(self, value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip()) \
            and len(value) <= 128

    def create_confirmation(self, confirmation_id: Any, request_id: Any,
                            permission_id: Any, scope: Any, target: Any, *,
                            limits: Any = None, context_hash: Any = "",
                            expires_at: Any = None,
                            now: Any = 0.0) -> Tuple[bool, Any]:
        """Crée une demande PENDING liée à l'empreinte exacte. Sans effet."""
        for value in (confirmation_id, request_id, permission_id,
                      scope, target):
            if not isinstance(value, str) or not value.strip() \
                    or len(value) > 512:
                return False, "demande-invalide"
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "demande-invalide"
        if expires_at is not None and (
                not isinstance(expires_at, (int, float))
                or isinstance(expires_at, bool)):
            return False, "demande-invalide"
        if confirmation_id in self._confirmations:
            return False, "doublon"
        fingerprint = demand_fingerprint(
            request_id=request_id, permission_id=permission_id,
            scope=scope, target=target, limits=limits,
            context_hash=context_hash if isinstance(context_hash, str)
            else "")
        stored_limits: Tuple[Tuple[str, str], ...] = ()
        if isinstance(limits, dict):
            stored_limits = tuple(sorted(
                (str(key), str(limits[key])) for key in limits))
        confirmation = Confirmation(
            confirmation_id=confirmation_id, request_id=request_id,
            permission_id=permission_id, scope=scope, target=target,
            fingerprint=fingerprint,
            context_hash=context_hash if isinstance(context_hash, str)
            else "",
            limits=stored_limits,
            expires_at=float(expires_at) if expires_at is not None else None,
            state="PENDING")
        self._confirmations[confirmation_id] = confirmation
        self._log("CREATE", confirmation_id, "system", float(now), "ok")
        return True, confirmation

    def _live(self, confirmation_id: str,
              now: float) -> Tuple[Optional[Confirmation], str]:
        current = self._confirmations.get(confirmation_id)
        if current is None:
            return None, "inconnue"
        if current.state == "PENDING" and current.expires_at is not None \
                and float(now) > float(current.expires_at):
            expired = Confirmation(
                confirmation_id=current.confirmation_id,
                request_id=current.request_id,
                permission_id=current.permission_id, scope=current.scope,
                target=current.target, fingerprint=current.fingerprint,
                context_hash=current.context_hash, limits=current.limits,
                expires_at=current.expires_at, state="EXPIRED",
                decided_by=current.decided_by, decided_at=current.decided_at,
                reason="expiree")
            self._confirmations[confirmation_id] = expired
            self._log("EXPIRE", confirmation_id, "system", float(now),
                      "expiree")
            return expired, "expiree"
        return current, "ok"

    def approve_confirmation(self, confirmation_id: Any, decided_by: Any,
                             demand_fingerprint: Any, *,
                             now: Any = 0.0) -> Tuple[bool, Any]:
        """APPROVE humain explicite, demande exacte seulement. Sans effet."""
        if not self._valid_id(confirmation_id) or not self._valid_id(
                decided_by):
            return False, "approbateur-requis"
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "demande-invalide"
        current, _ = self._live(str(confirmation_id), float(now))
        if current is None:
            return False, "inconnue"
        if current.state != "PENDING":
            return False, "etat-non-approuvable"
        if demand_fingerprint != current.fingerprint:
            return False, "demande-modifiee"
        approved = Confirmation(
            confirmation_id=current.confirmation_id,
            request_id=current.request_id,
            permission_id=current.permission_id, scope=current.scope,
            target=current.target, fingerprint=current.fingerprint,
            context_hash=current.context_hash, limits=current.limits,
            expires_at=current.expires_at, state="APPROVED",
            decided_by=decided_by.strip()[:128], decided_at=float(now),
            reason="approuve")
        self._confirmations[str(confirmation_id)] = approved
        self._log("APPROVE", str(confirmation_id), decided_by.strip()[:128],
                  float(now), "approuve")
        return True, approved

    def deny_confirmation(self, confirmation_id: Any, decided_by: Any, *,
                          reason: Any = "", now: Any = 0.0) -> Tuple[bool, Any]:
        """DENY idempotent sur PENDING/DENIED. Jamais d'exécution."""
        if not self._valid_id(confirmation_id) or not self._valid_id(
                decided_by):
            return False, "approbateur-requis"
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "demande-invalide"
        current, _ = self._live(str(confirmation_id), float(now))
        if current is None:
            return False, "inconnue"
        if current.state == "DENIED":
            return True, current
        if current.state != "PENDING":
            return False, "etat-non-refusable"
        denied = Confirmation(
            confirmation_id=current.confirmation_id,
            request_id=current.request_id,
            permission_id=current.permission_id, scope=current.scope,
            target=current.target, fingerprint=current.fingerprint,
            context_hash=current.context_hash, limits=current.limits,
            expires_at=current.expires_at, state="DENIED",
            decided_by=decided_by.strip()[:128], decided_at=float(now),
            reason=str(reason or "")[:256] or "refuse")
        self._confirmations[str(confirmation_id)] = denied
        self._log("DENY", str(confirmation_id), decided_by.strip()[:128],
                  float(now), denied.reason)
        return True, denied

    def consume_confirmation(self, confirmation_id: Any,
                             demand_fingerprint: Any, *,
                             now: Any = 0.0) -> Tuple[bool, Any]:
        """Consommation atomique unique : APPROVED → CONSUMED, irréversible."""
        if not self._valid_id(confirmation_id):
            return False, "inconnue"
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "demande-invalide"
        current, _ = self._live(str(confirmation_id), float(now))
        if current is None:
            return False, "inconnue"
        if current.state != "APPROVED":
            return False, "non-consommable"
        if demand_fingerprint != current.fingerprint:
            return False, "demande-modifiee"
        consumed = Confirmation(
            confirmation_id=current.confirmation_id,
            request_id=current.request_id,
            permission_id=current.permission_id, scope=current.scope,
            target=current.target, fingerprint=current.fingerprint,
            context_hash=current.context_hash, limits=current.limits,
            expires_at=current.expires_at, state="CONSUMED",
            decided_by=current.decided_by, decided_at=current.decided_at,
            reason="consommee")
        self._confirmations[str(confirmation_id)] = consumed
        self._log("CONSUME", str(confirmation_id), current.decided_by,
                  float(now), "consommee")
        return True, consumed

    def get(self, confirmation_id: str) -> Optional[Confirmation]:
        """Lecture seule."""
        return self._confirmations.get(confirmation_id)

    def audit(self) -> List[GateEvent]:
        """Journal interne, ordre de séquence. Lecture seule."""
        return list(self._events)
