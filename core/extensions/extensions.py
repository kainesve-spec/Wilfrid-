"""Wilfrid — extensions déclarées (Master 6) : registre d'inventaire, sans pouvoir.

Une extension est une fiche : identité, version, provenance, capacités
demandées, ressources, dépendances, contraintes. Le registre suit son cycle
de vie (DISCOVERED → VERIFIED → INSTALLED → ENABLED → AUTHORIZED/UNAUTHORIZED
→ SUSPENDED/REVOKED) par transitions explicites et vérifiées. Aucune
transition ne crée une permission : `authorize()` exige un approbateur humain
explicite (`approved_by` non vide) et ne fait qu'enregistrer cet état —
l'autorité réelle reste hors de ce module (gouverneur, registre P7).

Isolation : le registre ne contient que des données ; aucun import de
`core.p7`, `core.session`, `core.memory` ou autre moteur ; aucune exécution,
réseau, subprocess ou écriture autre que sa propre mémoire vive (aucune
persistance implicite : l'appelant sauvegarde explicitement via `snapshot()`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

EXTENSION_STATES = (
    "DISCOVERED",
    "VERIFIED",
    "INSTALLED",
    "ENABLED",
    "AUTHORIZED",
    "UNAUTHORIZED",
    "SUSPENDED",
    "REVOKED",
)

_EXTENSION_TRANSITIONS = {
    "DISCOVERED": ("VERIFIED", "REVOKED"),
    "VERIFIED": ("INSTALLED", "REVOKED"),
    "INSTALLED": ("ENABLED", "REVOKED"),
    "ENABLED": ("AUTHORIZED", "UNAUTHORIZED", "SUSPENDED", "REVOKED"),
    "AUTHORIZED": ("SUSPENDED", "REVOKED"),
    "UNAUTHORIZED": ("REVOKED",),
    "SUSPENDED": ("ENABLED", "REVOKED"),
    "REVOKED": (),
}


@dataclass(frozen=True)
class CapabilityDeclaration:
    """Capacité déclarée : nom, version, ressources, contraintes. Sans effet."""

    name: str = ""
    version: str = ""
    resources: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionDescriptor:
    """Fiche d'extension : identité, provenance, déclarations, état."""

    id: str = ""
    version: str = ""
    provenance: str = ""
    capabilities: Tuple[CapabilityDeclaration, ...] = ()
    resources: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    state: str = "DISCOVERED"
    approved_by: str = ""
    reason: str = ""


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


def _valid_version(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > 32:
        return False
    return all(part.isdigit() for part in value.strip().split(".") if part)


def verify_descriptor(descriptor: Any) -> Tuple[bool, str]:
    """Vérification structurelle + provenance : pur, sans effet."""
    if not isinstance(descriptor, ExtensionDescriptor):
        return False, "descriptor-invalide"
    if not _valid_id(descriptor.id):
        return False, "identite-invalide"
    if not _valid_version(descriptor.version):
        return False, "version-invalide"
    if not isinstance(descriptor.provenance, str) \
            or not descriptor.provenance.strip():
        return False, "provenance-manquante"
    for capability in descriptor.capabilities:
        if not isinstance(capability, CapabilityDeclaration):
            return False, "capacite-invalide"
        if not _valid_id(capability.name):
            return False, "capacite-invalide"
    for dep in descriptor.dependencies:
        if not isinstance(dep, str) or not dep.strip():
            return False, "dependance-invalide"
    return True, "ok"


class ExtensionRegistry:
    """Inventaire en mémoire vive. Aucune permission, aucune exécution."""

    def __init__(self) -> None:
        self._entries: Dict[str, ExtensionDescriptor] = {}

    def discover(self, descriptor: ExtensionDescriptor) -> Tuple[bool, str]:
        """Enregistre une fiche DISCOVERED. Ne vérifie pas, n'active pas."""
        if not isinstance(descriptor, ExtensionDescriptor):
            return False, "descriptor-invalide"
        if not _valid_id(descriptor.id):
            return False, "identite-invalide"
        if descriptor.id in self._entries:
            return False, "doublon"
        stored = ExtensionDescriptor(
            id=descriptor.id, version=descriptor.version,
            provenance=descriptor.provenance,
            capabilities=descriptor.capabilities,
            resources=descriptor.resources,
            dependencies=descriptor.dependencies,
            constraints=descriptor.constraints, state="DISCOVERED")
        self._entries[stored.id] = stored
        return True, "ok"

    def get(self, extension_id: str) -> Optional[ExtensionDescriptor]:
        record = self._entries.get(extension_id)
        return record

    def transition(self, extension_id: str,
                   target: str) -> Tuple[bool, str]:
        """Transition explicite vérifiée. Jamais d'activation implicite."""
        current = self._entries.get(extension_id)
        if current is None:
            return False, "inconnue"
        if target not in _EXTENSION_TRANSITIONS.get(current.state, ()):
            return False, "transition-invalide"
        if target == "ENABLED":
            for dep in current.dependencies:
                other = self._entries.get(dep)
                if other is None or other.state == "REVOKED":
                    return False, f"dependance-manquante:{dep}"
        updated = ExtensionDescriptor(
            id=current.id, version=current.version,
            provenance=current.provenance, capabilities=current.capabilities,
            resources=current.resources, dependencies=current.dependencies,
            constraints=current.constraints, state=target,
            approved_by=current.approved_by, reason=current.reason)
        self._entries[extension_id] = updated
        return True, "ok"

    def authorize(self, extension_id: str, approved_by: Any,
                  reason: Any = "") -> Tuple[bool, str]:
        """Marque AUTHORIZED sur approbation humaine explicite enregistrée.

        N'accorde aucune permission : seul l'état du registre change, et
        uniquement si l'extension est ENABLED et l'approbateur nommé.
        """
        current = self._entries.get(extension_id)
        if current is None:
            return False, "inconnue"
        if current.state != "ENABLED":
            return False, "etat-non-activable"
        if not isinstance(approved_by, str) or not approved_by.strip():
            return False, "approbateur-requis"
        updated = ExtensionDescriptor(
            id=current.id, version=current.version,
            provenance=current.provenance, capabilities=current.capabilities,
            resources=current.resources, dependencies=current.dependencies,
            constraints=current.constraints, state="AUTHORIZED",
            approved_by=approved_by.strip()[:128],
            reason=str(reason or "")[:256])
        self._entries[extension_id] = updated
        return True, "ok"

    def find_capability(self, name: Any) -> List[Tuple[str, str]]:
        """Fournisseurs déclarés d'une capacité (match exact). Lecture seule."""
        if not isinstance(name, str) or not name.strip():
            return []
        providers = [(record.id, record.version)
                     for record in self._entries.values()
                     if record.state not in ("REVOKED",)
                     for capability in record.capabilities
                     if capability.name == name]
        return sorted(set(providers))

    def snapshot(self) -> Dict[str, Any]:
        """État sérialisable (persistance explicite par l'appelant)."""
        return {"extensions": [
            {"id": record.id, "version": record.version,
             "provenance": record.provenance,
             "capabilities": [{"name": cap.name, "version": cap.version,
                               "resources": list(cap.resources),
                               "constraints": list(cap.constraints)}
                              for cap in record.capabilities],
             "resources": list(record.resources),
             "dependencies": list(record.dependencies),
             "constraints": list(record.constraints),
             "state": record.state, "approved_by": record.approved_by,
             "reason": record.reason}
            for record in sorted(self._entries.values(),
                                 key=lambda record: record.id)]}
