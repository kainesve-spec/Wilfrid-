"""Wilfrid — agents spécialisés (Master 6) : propositions sans autorité.

Un agent produit des propositions/résultats enregistrés comme données. Il ne
décide jamais de l'autorité finale : aucun résultat n'exécute, n'approuve ni
n'attribue quoi que ce soit. Les conflits (plusieurs résultats distincts pour
une même tâche) restent explicites : listés, jamais arbitrés ni fusionnés.

Même discipline que les extensions : données en mémoire vive, transitions
explicites, déterminisme total, aucune exécution/réseau/subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

AGENT_STATES = (
    "DECLARED",
    "VERIFIED",
    "ACTIVE",
    "SUSPENDED",
    "REVOKED",
)

_AGENT_TRANSITIONS = {
    "DECLARED": ("VERIFIED", "REVOKED"),
    "VERIFIED": ("ACTIVE", "REVOKED"),
    "ACTIVE": ("SUSPENDED", "REVOKED"),
    "SUSPENDED": ("ACTIVE", "REVOKED"),
    "REVOKED": (),
}


@dataclass(frozen=True)
class AgentDescriptor:
    """Fiche d'agent : identité, provenance, spécialité, état."""

    id: str = ""
    version: str = ""
    provenance: str = ""
    specialty: str = ""
    state: str = "DECLARED"
    reason: str = ""


@dataclass(frozen=True)
class AgentResult:
    """Proposition enregistrée : données horodatées par compteur, sans effet."""

    agent_id: str = ""
    task_id: str = ""
    content: str = ""
    sequence: int = 0


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


class AgentRegistry:
    """Registre d'agents + résultats. Aucune décision d'autorité."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentDescriptor] = {}
        self._results: List[AgentResult] = []
        self._sequence = 0

    def declare(self, descriptor: AgentDescriptor) -> Tuple[bool, str]:
        if not isinstance(descriptor, AgentDescriptor):
            return False, "descriptor-invalide"
        if not _valid_id(descriptor.id):
            return False, "identite-invalide"
        if not isinstance(descriptor.provenance, str) \
                or not descriptor.provenance.strip():
            return False, "provenance-manquante"
        if descriptor.id in self._agents:
            return False, "doublon"
        self._agents[descriptor.id] = AgentDescriptor(
            id=descriptor.id, version=descriptor.version,
            provenance=descriptor.provenance,
            specialty=descriptor.specialty, state="DECLARED")
        return True, "ok"

    def transition(self, agent_id: str, target: str) -> Tuple[bool, str]:
        current = self._agents.get(agent_id)
        if current is None:
            return False, "inconnu"
        if target not in _AGENT_TRANSITIONS.get(current.state, ()):
            return False, "transition-invalide"
        self._agents[agent_id] = AgentDescriptor(
            id=current.id, version=current.version,
            provenance=current.provenance, specialty=current.specialty,
            state=target, reason=current.reason)
        return True, "ok"

    def get(self, agent_id: str) -> Optional[AgentDescriptor]:
        return self._agents.get(agent_id)

    def submit_result(self, agent_id: str, task_id: str,
                      content: Any) -> Tuple[bool, Any]:
        """Enregistre une proposition comme donnée. Agent ACTIF requis."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False, "agent-inconnu"
        if agent.state != "ACTIVE":
            return False, "agent-non-actif"
        if not _valid_id(task_id) or not isinstance(content, str) \
                or not content.strip() or len(content) > 4000:
            return False, "resultat-invalide"
        self._sequence += 1
        record = AgentResult(agent_id=agent_id, task_id=task_id,
                             content=content, sequence=self._sequence)
        self._results.append(record)
        return True, record

    def results_for(self, task_id: str) -> List[AgentResult]:
        """Résultats d'une tâche, ordre de soumission. Lecture seule."""
        return [record for record in self._results
                if record.task_id == task_id]

    def conflicts(self, task_id: str) -> List[List[AgentResult]]:
        """Groupes de résultats distincts : conflit explicite, non arbitré."""
        seen: Dict[str, AgentResult] = {}
        for record in self.results_for(task_id):
            seen.setdefault(record.content, record)
        if len(seen) < 2:
            return []
        return [[record] for record in sorted(seen.values(),
                                              key=lambda record: record.sequence)]

    def snapshot(self) -> Dict[str, Any]:
        """État sérialisable (persistance explicite par l'appelant)."""
        return {
            "agents": [{"id": agent.id, "version": agent.version,
                        "provenance": agent.provenance,
                        "specialty": agent.specialty, "state": agent.state}
                       for agent in sorted(self._agents.values(),
                                          key=lambda agent: agent.id)],
            "results": [{"agent_id": record.agent_id,
                         "task_id": record.task_id,
                         "content": record.content,
                         "sequence": record.sequence}
                        for record in self._results],
        }
