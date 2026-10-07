"""Wilfrid — mandats opérationnels R2 (registre humain, sans exécution).

Un mandat est créé/modifié/suspendu/révoqué/renouvelé UNIQUEMENT par décision
humaine explicite (`decided_by` nommé, enregistré). Il borne : capabilities
exactes, ressources exactes, opérations exactes, plafonds, conditions de
contexte, validité temporelle. L'évaluation produit ALLOW_R2,
REQUIRE_CONFIRMATION, DENY ou DEFER — jamais d'exécution, jamais d'extension :
hors mandat = pas d'ALLOW_R2 ; révocation/suspension/expiration = pas d'ALLOW_R2 ;
capability inconnue = DENY (aucun chemin confirmable). `authorize_execution`
re-vérifie l'état courant avant de lier une demande exacte (empreinte) :
un ancien ALLOW_R2 ne vaut jamais autorisation permanente.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.p7.approval_gate import demand_fingerprint

MANDATE_STATES = ("ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED")

_MANDATE_TRANSITIONS = {
    "ACTIVE": ("SUSPENDED", "REVOKED"),
    "SUSPENDED": ("ACTIVE", "REVOKED"),
    "EXPIRED": (),
    "REVOKED": (),
}

_KNOWN_CAPABILITIES = (
    "P7.CATALOG_READ",
    "P7.JAIL_READ",
    "P7.JAIL_WRITE_REVERSIBLE",
    "P7.NOTIFY_LOCAL",
)


@dataclass(frozen=True)
class Mandate:
    """Mandat : bornes exactes + validité + provenance humaine."""

    mandate_id: str = ""
    decided_by: str = ""
    capabilities: Tuple[str, ...] = ()
    resources: Tuple[str, ...] = ()
    operations: Tuple[str, ...] = ()
    limits: Tuple[Tuple[str, str], ...] = ()
    conditions: Tuple[Tuple[str, str], ...] = ()
    valid_from: float = 0.0
    expires_at: float = 0.0
    state: str = "ACTIVE"
    version: int = 1
    provenance: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class MandateDecision:
    """Décision d'évaluation : fermée, motivée, bornée."""

    decision: str = "DENY"
    mandate_id: str = ""
    reason: str = ""
    applied_limits: Tuple[Tuple[str, str], ...] = ()
    request_id: str = ""


@dataclass(frozen=True)
class MandateEvent:
    """Trace : séquence + événement + acteur humain, sans secret."""

    seq: int = 0
    event: str = ""
    mandate_id: str = ""
    actor: str = ""
    timestamp: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class MandateAuthorization:
    """Artefact lié à UNE demande exacte : non réutilisable ailleurs."""

    mandate_id: str = ""
    demand_fingerprint: str = ""
    expires_at: float = 0.0
    version: int = 0


def _short(text: str, limit: int) -> str:
    return str(text)[:limit]


def _mandate_fingerprint(mandate_id: str, decided_by: str,
                         capabilities: Tuple[str, ...],
                         resources: Tuple[str, ...],
                         operations: Tuple[str, ...],
                         limits: Tuple[Tuple[str, str], ...],
                         conditions: Tuple[Tuple[str, str], ...],
                         valid_from: float, expires_at: float,
                         version: int) -> str:
    canonical = "|".join([
        mandate_id, decided_by,
        ",".join(sorted(capabilities)), ",".join(sorted(resources)),
        ",".join(sorted(operations)),
        ",".join(f"{key}={value}" for key, value in sorted(limits)),
        ",".join(f"{key}={value}" for key, value in sorted(conditions)),
        repr(valid_from), repr(expires_at), str(version)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clean_str(value: Any, limit: int) -> Optional[str]:
    if not isinstance(value, str) or not value.strip() \
            or len(value) > limit:
        return None
    return value.strip()


def _clean_tuple(items: Any, limit: int, item_limit: int) -> Optional[tuple]:
    if not isinstance(items, (tuple, list)):
        return None
    cleaned = []
    for item in items:
        if not isinstance(item, str) or not item.strip() \
                or len(item) > item_limit:
            return None
        cleaned.append(item.strip())
    if len(cleaned) > limit:
        return None
    return tuple(cleaned)


def _clean_mapping(mapping: Any, limit: int) -> Optional[tuple]:
    if mapping is None:
        return ()
    if not isinstance(mapping, dict):
        return None
    items = []
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 64:
            return None
        text = str(value)
        if len(text) > 256:
            return None
        items.append((key.strip(), text))
    if len(items) > limit:
        return None
    return tuple(sorted(items))


class MandateRegistry:
    """Registre des mandats. Mutations humaines explicites uniquement."""

    def __init__(self) -> None:
        self._mandates: Dict[str, Mandate] = {}
        self._events: List[MandateEvent] = []
        self._seq = 0

    def _log(self, event: str, mandate_id: str, actor: str,
             timestamp: float, reason: str = "") -> None:
        self._seq += 1
        self._events.append(MandateEvent(
            seq=self._seq, event=event, mandate_id=_short(mandate_id, 128),
            actor=_short(actor, 128), timestamp=float(timestamp),
            reason=_short(reason, 256)))

    def _human(self, decided_by: Any) -> Optional[str]:
        if not isinstance(decided_by, str) or not decided_by.strip() \
                or len(decided_by) > 128:
            return None
        return decided_by.strip()

    def create(self, mandate_id: Any, decided_by: Any, *,
               capabilities: Any = (), resources: Any = (),
               operations: Any = (), limits: Any = None,
               conditions: Any = None, valid_from: Any = 0.0,
               expires_at: Any = None, provenance: Any = "",
               now: Any = 0.0) -> Tuple[bool, Any]:
        """Crée un mandat ACTIVE. Expiration finie obligatoire."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        mid = _clean_str(mandate_id, 128)
        human = self._human(decided_by)
        if mid is None or human is None:
            return False, "mandat-invalide"
        if mid in self._mandates:
            return False, "doublon"
        caps = _clean_tuple(capabilities, 16, 128)
        ress = _clean_tuple(resources, 64, 512)
        ops = _clean_tuple(operations, 16, 64)
        lims = _clean_mapping(limits, 32)
        conds = _clean_mapping(conditions, 32)
        if caps is None or not caps or ress is None or not ress \
                or ops is None or not ops or lims is None or conds is None:
            return False, "mandat-invalide"
        if any(cap not in _KNOWN_CAPABILITIES for cap in caps):
            return False, "capability-inconnue"
        if not isinstance(valid_from, (int, float)) \
                or isinstance(valid_from, bool):
            return False, "mandat-invalide"
        if not isinstance(expires_at, (int, float)) \
                or isinstance(expires_at, bool) \
                or float(expires_at) <= float(now):
            return False, "expiration-invalide"
        if not isinstance(provenance, str) or len(provenance) > 256:
            return False, "mandat-invalide"
        fingerprint = _mandate_fingerprint(
            mid, human, caps, ress, ops, lims, conds, float(valid_from),
            float(expires_at), 1)
        mandate = Mandate(
            mandate_id=mid, decided_by=human, capabilities=caps,
            resources=ress, operations=ops, limits=lims, conditions=conds,
            valid_from=float(valid_from), expires_at=float(expires_at),
            state="ACTIVE", version=1, provenance=provenance.strip(),
            fingerprint=fingerprint)
        self._mandates[mid] = mandate
        self._log("CREATE", mid, human, float(now), "cree")
        return True, mandate

    def get(self, mandate_id: str) -> Optional[Mandate]:
        """Lecture seule."""
        return self._mandates.get(mandate_id)

    def mandate_ids(self) -> Tuple[str, ...]:
        """Identifiants triés (évaluation déterministe). Lecture seule."""
        return tuple(sorted(self._mandates))

    def verify_integrity(self, mandate_id: str) -> Tuple[bool, str]:
        """Recalcule l'empreinte : toute mutation furtive est détectée."""
        current = self._mandates.get(mandate_id)
        if current is None:
            return False, "inconnu"
        expected = _mandate_fingerprint(
            current.mandate_id, current.decided_by, current.capabilities,
            current.resources, current.operations, current.limits,
            current.conditions, current.valid_from, current.expires_at,
            current.version)
        if expected != current.fingerprint:
            return False, "integrite-compromise"
        return True, "ok"

    def _set_state(self, mandate_id: str, decided_by: str, target: str,
                   now: float, event: str) -> Tuple[bool, Any]:
        human = self._human(decided_by)
        current = self._mandates.get(mandate_id)
        if current is None:
            return False, "inconnu"
        if human is None:
            return False, "approbateur-requis"
        if target not in _MANDATE_TRANSITIONS.get(current.state, ()):
            return False, "transition-invalide"
        updated = Mandate(
            mandate_id=current.mandate_id, decided_by=current.decided_by,
            capabilities=current.capabilities, resources=current.resources,
            operations=current.operations, limits=current.limits,
            conditions=current.conditions, valid_from=current.valid_from,
            expires_at=current.expires_at, state=target,
            version=current.version, provenance=current.provenance,
            fingerprint=current.fingerprint)
        self._mandates[mandate_id] = updated
        self._log(event, mandate_id, human, float(now), target.lower())
        return True, updated

    def suspend(self, mandate_id: str, decided_by: Any,
                now: Any = 0.0) -> Tuple[bool, Any]:
        """ACTIVE → SUSPENDED, décision humaine."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        return self._set_state(str(mandate_id), decided_by, "SUSPENDED",
                               float(now), "SUSPEND")

    def resume(self, mandate_id: str, decided_by: Any,
               now: Any = 0.0) -> Tuple[bool, Any]:
        """SUSPENDED → ACTIVE, décision humaine."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        current = self._mandates.get(str(mandate_id))
        if current is None:
            return False, "inconnu"
        human = self._human(decided_by)
        if human is None:
            return False, "approbateur-requis"
        if current.state != "SUSPENDED":
            return False, "transition-invalide"
        updated = Mandate(
            mandate_id=current.mandate_id, decided_by=current.decided_by,
            capabilities=current.capabilities, resources=current.resources,
            operations=current.operations, limits=current.limits,
            conditions=current.conditions, valid_from=current.valid_from,
            expires_at=current.expires_at, state="ACTIVE",
            version=current.version, provenance=current.provenance,
            fingerprint=current.fingerprint)
        self._mandates[str(mandate_id)] = updated
        self._log("RESUME", str(mandate_id), human, float(now), "actif")
        return True, updated

    def revoke(self, mandate_id: str, decided_by: Any,
               now: Any = 0.0) -> Tuple[bool, Any]:
        """ACTIVE/SUSPENDED → REVOKED, terminal et irréversible."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        return self._set_state(str(mandate_id), decided_by, "REVOKED",
                               float(now), "REVOKE")

    def amend(self, mandate_id: str, decided_by: Any, *,
              capabilities: Any = None, resources: Any = None,
              operations: Any = None, limits: Any = None,
              conditions: Any = None, now: Any = 0.0) -> Tuple[bool, Any]:
        """Modifie les bornes (version+1, empreinte recalculée), humain requis."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        current = self._mandates.get(str(mandate_id))
        if current is None:
            return False, "inconnu"
        human = self._human(decided_by)
        if human is None:
            return False, "approbateur-requis"
        if current.state not in ("ACTIVE", "SUSPENDED"):
            return False, "etat-fige"
        caps = current.capabilities if capabilities is None else \
            _clean_tuple(capabilities, 16, 128)
        ress = current.resources if resources is None else \
            _clean_tuple(resources, 64, 512)
        ops = current.operations if operations is None else \
            _clean_tuple(operations, 16, 64)
        lims = current.limits if limits is None else \
            _clean_mapping(limits, 32)
        conds = current.conditions if conditions is None else \
            _clean_mapping(conditions, 32)
        if caps is None or not caps or ress is None or not ress \
                or ops is None or not ops or lims is None or conds is None:
            return False, "mandat-invalide"
        if any(cap not in _KNOWN_CAPABILITIES for cap in caps):
            return False, "capability-inconnue"
        version = current.version + 1
        updated = Mandate(
            mandate_id=current.mandate_id, decided_by=current.decided_by,
            capabilities=caps, resources=ress, operations=ops, limits=lims,
            conditions=conds, valid_from=current.valid_from,
            expires_at=current.expires_at, state=current.state,
            version=version, provenance=current.provenance,
            fingerprint=_mandate_fingerprint(
                current.mandate_id, current.decided_by, caps, ress, ops,
                lims, conds, current.valid_from, current.expires_at,
                version))
        self._mandates[str(mandate_id)] = updated
        self._log("AMEND", str(mandate_id), human, float(now),
                  f"version-{version}")
        return True, updated

    def renew(self, mandate_id: str, decided_by: Any, new_expires_at: Any,
              now: Any = 0.0) -> Tuple[bool, Any]:
        """Prolonge l'expiration (version+1), humain requis. Jamais implicite."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return False, "mandat-invalide"
        current = self._mandates.get(str(mandate_id))
        if current is None:
            return False, "inconnu"
        human = self._human(decided_by)
        if human is None:
            return False, "approbateur-requis"
        if current.state not in ("ACTIVE", "SUSPENDED"):
            return False, "etat-fige"
        if not isinstance(new_expires_at, (int, float)) \
                or isinstance(new_expires_at, bool) \
                or float(new_expires_at) <= float(now):
            return False, "expiration-invalide"
        version = current.version + 1
        updated = Mandate(
            mandate_id=current.mandate_id, decided_by=current.decided_by,
            capabilities=current.capabilities, resources=current.resources,
            operations=current.operations, limits=current.limits,
            conditions=current.conditions, valid_from=current.valid_from,
            expires_at=float(new_expires_at), state=current.state,
            version=version, provenance=current.provenance,
            fingerprint=_mandate_fingerprint(
                current.mandate_id, current.decided_by,
                current.capabilities, current.resources, current.operations,
                current.limits, current.conditions, current.valid_from,
                float(new_expires_at), version))
        self._mandates[str(mandate_id)] = updated
        self._log("RENEW", str(mandate_id), human, float(now),
                  f"version-{version}")
        return True, updated

    def _expire_if_past(self, mandate_id: str,
                        now: float) -> Optional[Mandate]:
        current = self._mandates.get(mandate_id)
        if current is None or current.state not in ("ACTIVE", "SUSPENDED"):
            return current
        if float(now) > float(current.expires_at):
            updated = Mandate(
                mandate_id=current.mandate_id,
                decided_by=current.decided_by,
                capabilities=current.capabilities,
                resources=current.resources, operations=current.operations,
                limits=current.limits, conditions=current.conditions,
                valid_from=current.valid_from,
                expires_at=current.expires_at, state="EXPIRED",
                version=current.version, provenance=current.provenance,
                fingerprint=current.fingerprint)
            self._mandates[mandate_id] = updated
            self._log("EXPIRE", mandate_id, "system", float(now), "expiree")
            return updated
        return current

    def evaluate(self, mandate_id: Any, *, capability: Any, resource: Any,
                 operation: Any, params: Any = None, context: Any = None,
                 request_id: Any = "", now: Any = 0.0) -> MandateDecision:
        """Évalue une demande contre UN mandat. Aucune exécution."""
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            return MandateDecision("DENY", "", "demande-invalide", (),
                                   str(request_id or ""))
        rid = request_id if isinstance(request_id, str) else ""
        current = self._mandates.get(str(mandate_id)) \
            if isinstance(mandate_id, str) else None
        if current is None:
            if isinstance(capability, str) and capability in _KNOWN_CAPABILITIES:
                return MandateDecision("REQUIRE_CONFIRMATION", "",
                                       "sans-mandat", (), rid)
            return MandateDecision("DENY", "", "capability-inconnue", (), rid)
        current = self._expire_if_past(str(mandate_id), float(now))
        if current is None or current.state != "ACTIVE":
            if isinstance(capability, str) \
                    and capability in _KNOWN_CAPABILITIES:
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id if current else "",
                                       "mandat-non-actif", (), rid)
            return MandateDecision("DENY",
                                   current.mandate_id if current else "",
                                   "mandat-non-actif", (), rid)
        if not isinstance(capability, str) \
                or capability not in current.capabilities:
            if isinstance(capability, str) \
                    and capability in _KNOWN_CAPABILITIES:
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id,
                                       "hors-mandat", (), rid)
            return MandateDecision("DENY", current.mandate_id,
                                   "capability-inconnue", (), rid)
        if not isinstance(resource, str) or resource not in current.resources:
            return MandateDecision("REQUIRE_CONFIRMATION", current.mandate_id,
                                   "hors-perimetre", (), rid)
        if not isinstance(operation, str) or operation not in current.operations:
            return MandateDecision("REQUIRE_CONFIRMATION", current.mandate_id,
                                   "operation-non-couverte", (), rid)
        applied: List[Tuple[str, str]] = []
        given = params if isinstance(params, dict) else {}
        for key, ceiling in current.limits:
            if key not in given:
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id,
                                       f"parametre-manquant:{key}", (), rid)
            try:
                value = float(given[key])
            except (TypeError, ValueError):
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id,
                                       f"parametre-invalide:{key}", (), rid)
            try:
                bound = float(ceiling)
            except (TypeError, ValueError):
                return MandateDecision("DENY", current.mandate_id,
                                       "limite-invalide", (), rid)
            if not value <= bound:
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id,
                                       f"plafond-depasse:{key}", (), rid)
            applied.append((key, str(given[key])))
        extra = [key for key in given if key not in dict(current.limits)]
        if extra:
            return MandateDecision("REQUIRE_CONFIRMATION", current.mandate_id,
                                   "parametre-non-examine", (), rid)
        context_given = context if isinstance(context, dict) else {}
        for key, expected in current.conditions:
            if context_given.get(key) != expected:
                return MandateDecision("REQUIRE_CONFIRMATION",
                                       current.mandate_id,
                                       "contexte-incompatible", (), rid)
        return MandateDecision("ALLOW_R2", current.mandate_id, "couvert",
                               tuple(sorted(applied)), rid)

    def authorize_execution(self, mandate_id: Any, *,
                            capability: Any, resource: Any, operation: Any,
                            params: Any = None, context: Any = None,
                            request_id: Any = "",
                            now: Any = 0.0) -> Tuple[bool, Any]:
        """Lie UNE demande exacte à un mandat valide (re-vérifié ici même).

        Un ancien ALLOW_R2 ne vaut rien seul : l'état est relu, l'expiration
        appliquée, puis l'artefact est scellé par l'empreinte de la demande.
        Toute réutilisation pour une autre demande échoue au contrôle.
        """
        decision = self.evaluate(
            mandate_id, capability=capability, resource=resource,
            operation=operation, params=params, context=context,
            request_id=request_id, now=now)
        if decision.decision != "ALLOW_R2":
            return False, decision.reason
        current = self._mandates.get(str(mandate_id))
        if current is None or current.state != "ACTIVE":
            return False, "mandat-non-actif"
        try:
            fingerprint = demand_fingerprint(
                request_id=decision.request_id,
                permission_id=capability if isinstance(capability, str)
                else "",
                scope=str(resource) if isinstance(resource, str) else "",
                target=str(resource) if isinstance(resource, str) else "",
                limits=dict(decision.applied_limits),
                context_hash="")
        except Exception:
            return False, "empreinte-impossible"
        self._log("AUTHORIZE", str(mandate_id), current.decided_by,
                  float(now) if isinstance(now, (int, float))
                  and not isinstance(now, bool) else 0.0,
                  "artefact-lie")
        return True, MandateAuthorization(
            mandate_id=current.mandate_id, demand_fingerprint=fingerprint,
            expires_at=current.expires_at, version=current.version)

    def audit(self) -> List[MandateEvent]:
        """Journal interne, ordre de séquence. Lecture seule."""
        return list(self._events)
