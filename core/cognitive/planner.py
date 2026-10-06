"""Wilfrid — planner abstrait P5 (données uniquement, jamais d'exécution).

Un plan décrit une action potentielle ; il ne l'exécute jamais : aucune
commande, shell, réseau, navigateur, fichier, TAIOS, trade ou outil
externe ici — seulement des étapes nommées avec préconditions typées.
"""

from __future__ import annotations

import re
from typing import Dict, List

from core.cognitive.types import CognitiveOutput, IntentKind

MAX_STEPS = 8
MAX_STEP_CHARS = 80

_SPLIT_RE = re.compile(
    r"\s*(?:puis|ensuite|et puis|après|after that|then|;|,)\s*",
    re.IGNORECASE,
)


def _step(name: str, requires: List[str], index: int) -> Dict[str, str]:
    return {
        "index": str(index),
        "name": name[:MAX_STEP_CHARS],
        "requires": ",".join(requires),
        "expected": "",
    }


def build_plan(decision: CognitiveOutput, raw_text: str = "") -> List[Dict[str, str]]:
    """Construit un plan abstrait borné. Pur, déterministe, sans I/O."""
    kind = decision.kind
    if kind == IntentKind.NEED_ACTION:
        return [_step("action_requise", ["ACTION"], 0)]
    if kind == IntentKind.NEED_SEARCH:
        return [_step("recherche_requise", ["SEARCH"], 0)]
    if kind == IntentKind.NEED_TOOL:
        outil = decision.params.outil or "TOOL"
        return [_step("outil_requis", [outil.upper()], 0)]
    if kind == IntentKind.PLAN:
        parts = [p.strip() for p in _SPLIT_RE.split(raw_text) if p.strip()]
        if len(parts) <= 1:
            return [_step("analyser_la_demande", [], 0)]
        steps = []
        for i, part in enumerate(parts[:MAX_STEPS]):
            steps.append(_step(part, [], i))
        return steps
    return []


def plan_is_effect_free(plan: List[Dict[str, str]]) -> bool:
    """Garde-fous structurel : que des données (jamais d'exécutable)."""
    if len(plan) > MAX_STEPS:
        return False
    for step in plan:
        if not isinstance(step, dict):
            return False
        if set(step.keys()) != {"index", "name", "requires", "expected"}:
            return False
        if not all(isinstance(v, str) for v in step.values()):
            return False
        if len(step["name"]) > MAX_STEP_CHARS:
            return False
    return True
