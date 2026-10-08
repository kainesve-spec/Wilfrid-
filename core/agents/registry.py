"""Wilfrid — registre d'agents IA (états prouvés, sans autorité).

DECLARED → CONFIGURED → CONNECTED → OPERATIONAL (preuve réelle
exigée) ; FAILED, DISABLED. Un agent est une RESSOURCE : il propose,
jamais il n'autorise. Secrets par référence d'environnement uniquement,
valeurs jamais lues ici au-delà de la présence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

STATES = ("DECLARED", "CONFIGURED", "CONNECTED", "OPERATIONAL", "FAILED",
          "DISABLED")

PROVIDERS = ("OPENAI", "GEMINI", "CLAUDE", "OMNIROUTE")


@dataclass(frozen=True)
class Agent:
    """Fiche agent : accès, modèle, état, preuve (jamais de secret)."""

    id: str = ""
    provider: str = ""
    endpoint: str = ""
    model: str = ""
    auth_env: str = ""
    timeout_s: float = 20.0
    state: str = "DECLARED"
    last_error: str = ""
    proof: str = ""


@dataclass
class AgentRegistry:
    """Registre explicite (aucune détection automatique)."""

    agents: Dict[str, Agent] = field(default_factory=dict)

    def declare(self, agent: Agent) -> Tuple[bool, str]:
        """Déclare (données validées, sans effet, sans secret)."""
        if not isinstance(agent, Agent) or not agent.id.strip() \
                or len(agent.id) > 128:
            return False, "agent-invalide"
        if agent.provider not in PROVIDERS:
            return False, "provider-inconnu"
        if agent.id in self.agents:
            return False, "deja-declare"
        try:
            timeout = float(agent.timeout_s)
        except (TypeError, ValueError):
            return False, "delai-invalide"
        stored = Agent(
            id=agent.id.strip(), provider=agent.provider,
            endpoint=str(agent.endpoint)[:512],
            model=str(agent.model)[:128],
            auth_env=str(agent.auth_env)[:128],
            timeout_s=min(max(timeout, 1.0), 120.0), state="DECLARED")
        self.agents[stored.id] = stored
        return True, "declare"

    def configured(self, agent_id: str) -> bool:
        """Secret référencé présent (présence seule, valeur jamais lue)."""
        agent = self.agents.get(agent_id)
        if agent is None or not agent.auth_env:
            return False
        return bool((os.environ.get(agent.auth_env) or "").strip())

    def transition(self, agent_id: str, target: str, *,
                   proof: str = "", error: str = "") -> Tuple[bool, str]:
        """Transition explicite ; OPERATIONAL exige une preuve réelle."""
        current = self.agents.get(agent_id)
        if current is None:
            return False, "agent-inconnu"
        allowed = {"DECLARED": ("CONFIGURED", "DISABLED"),
                   "CONFIGURED": ("CONNECTED", "FAILED", "DISABLED"),
                   "CONNECTED": ("OPERATIONAL", "FAILED", "DISABLED"),
                   "OPERATIONAL": ("DISABLED", "FAILED"),
                   "FAILED": ("DISABLED",),
                   "DISABLED": ()}.get(current.state, ())
        if target not in allowed:
            return False, "transition-invalide"
        if target in ("CONFIGURED", "CONNECTED", "OPERATIONAL") \
                and not self.configured(agent_id):
            return False, "secret-absent"
        if target == "OPERATIONAL" and not proof.strip():
            return False, "preuve-requise"
        updated = Agent(
            id=current.id, provider=current.provider,
            endpoint=current.endpoint, model=current.model,
            auth_env=current.auth_env, timeout_s=current.timeout_s,
            state=target, last_error=str(error)[:256]
            if target == "FAILED" else "",
            proof=str(proof)[:256] if target == "OPERATIONAL" else "")
        self.agents[current.id] = updated
        return True, target.lower()

    def get(self, agent_id: str) -> Any:
        """Fiche exacte, `None` si inconnue."""
        return self.agents.get(agent_id)

    def list(self, state: str = "") -> Tuple[Agent, ...]:
        """Inventaire stable, filtré par état si demandé."""
        items = sorted(self.agents.values(), key=lambda a: a.id)
        if state:
            items = [a for a in items if a.state == state]
        return tuple(items)


def describe() -> Dict[str, Any]:
    """Contrat registre (sans effet)."""
    return {"providers": list(PROVIDERS), "etats": list(STATES),
            "secret": "reference-env-uniquement",
            "network": False, "authority": False}
