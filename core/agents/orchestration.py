"""Wilfrid — orchestration multi-agents (ressources, sans autorité).

Appel unique/multiples, seconde opinion, agrégation, comparaison. Les
agents proposent ; Wilfrid (Core + gouvernance) dispose. Minimisation
du contexte : nécessaire / facultatif / sensible / interdit — seuls
les champs nécessaires partent, secrets et données interdites jamais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from core.agents.providers import COMPLETERS, AgentResult
from core.agents.registry import Agent, AgentRegistry

FORBIDDEN_KEYS = ("key", "token", "secret", "password", "credential",
                  "api_key", "apikey", "auth", "bearer")
SENSITIVE_KEYS = ("souvenir", "memoire", "memory", "contact", "sms",
                  "localisation", "position", "sante", "financier",
                  "compte", "mot de passe")


@dataclass(frozen=True)
class Consultation:
    """Résultat d'orchestration : avis agrégés + provenance."""

    status: str = "FAILED"
    agent_ids: Tuple[str, ...] = ()
    texts: Tuple[str, ...] = ()
    detail: str = ""
    provenance: Tuple[str, ...] = ()


def minimize_context(context: Any) -> Dict[str, List[str]]:
    """Trie le contexte : nécessaire / facultatif / sensible / interdit."""
    required: List[str] = []
    optional: List[str] = []
    sensitive: List[str] = []
    forbidden: List[str] = []
    if not isinstance(context, dict):
        return {"required": [], "optional": [], "sensitive": [],
                "forbidden": ["contexte-invalide"]}
    for key, value in context.items():
        name = str(key).lower()
        if any(mark in name for mark in FORBIDDEN_KEYS):
            forbidden.append(str(key))
        elif any(mark in name for mark in SENSITIVE_KEYS):
            sensitive.append(str(key))
        elif isinstance(value, str) and value.strip():
            required.append(str(key))
        else:
            optional.append(str(key))
    return {"required": sorted(required), "optional": sorted(optional),
            "sensitive": sorted(sensitive), "forbidden": sorted(forbidden)}


def build_prompt(question: str, context: Any = None) -> str:
    """Prompt minimisé : question + champs nécessaires uniquement."""
    parts = [question.strip()] if isinstance(question, str) \
        and question.strip() else []
    buckets = minimize_context(context or {})
    if isinstance(context, dict):
        for key in buckets["required"]:
            value = context.get(key, "")
            if isinstance(value, str) and value.strip():
                parts.append("%s: %s" % (key, value.strip()[:500]))
    return "\n".join(parts)[:4000]


def consult(registry: AgentRegistry, agent_id: str, question: str, *,
            context: Any = None,
            complete_fn: Any = None) -> AgentResult:
    """Consulte un agent OPERATIONAL (sinon refus honnête)."""
    agent = registry.get(agent_id) if isinstance(registry,
                                                 AgentRegistry) else None
    if agent is None:
        return AgentResult(status="UNKNOWN", agent_id=str(agent_id),
                           detail="agent-inconnu")
    if agent.state != "OPERATIONAL":
        return AgentResult(status="UNAVAILABLE", agent_id=agent.id,
                           provider=agent.provider,
                           detail="agent-non-operationnel:" + agent.state)
    complete = complete_fn
    if complete is None:
        complete = COMPLETERS.get(agent.provider)
        if complete is None:
            return AgentResult(status="FAILED", agent_id=agent.id,
                               provider=agent.provider,
                               detail="provider-inconnu")
    prompt = build_prompt(question, context)
    if not prompt:
        return AgentResult(status="INVALID", agent_id=agent.id,
                           provider=agent.provider,
                           detail="question-invalide")
    try:
        return complete(agent, prompt)
    except Exception:
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider=agent.provider,
                           detail="erreur-adaptateur")


def consult_many(registry: AgentRegistry, agent_ids: Any, question: str, *,
                 context: Any = None,
                 complete_fn: Any = None) -> Consultation:
    """Avis multiples : succès agrégés, échecs listés, jamais d'invention."""
    ids = [aid for aid in (agent_ids or []) if isinstance(aid, str)]
    texts: List[str] = []
    used: List[str] = []
    problems: List[str] = []
    for aid in ids:
        result = consult(registry, aid, question, context=context,
                         complete_fn=complete_fn)
        if result.status == "SUCCESS":
            texts.append(result.text)
            used.append("%s/%s" % (result.provider, result.agent_id))
        else:
            problems.append("%s:%s" % (aid, result.status))
    if not texts:
        return Consultation(status="FAILED", agent_ids=tuple(ids),
                            detail=";".join(problems)[:300] or "aucun-avis")
    return Consultation(status="SUCCESS", agent_ids=tuple(used),
                        texts=tuple(texts),
                        detail=";".join(problems)[:300] or "tous-ok",
                        provenance=tuple(used))


def describe() -> Dict[str, Any]:
    """Contrat orchestration (sans effet)."""
    return {"modes": ["unique", "multiple", "seconde-opinion",
                       "agregation"],
            "autorite_externe": False, "network": False,
            "authority": False}
