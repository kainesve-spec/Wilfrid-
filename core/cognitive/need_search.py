"""Wilfrid — pont NEED_SEARCH → Knowledge O2 (adaptateur, sans autorité).

Relie une intention P5 déjà produite au pipeline O2 Local Retrieval :
`CognitiveOutput(NEED_SEARCH)` → `query_from_cognition()` → `retrieve()` →
`KnowledgeResult`. Ne classifie pas, ne devine aucune source, ne crée aucune
approbation/permission, n'appelle ni P7 ni le réseau : si `query_from_cognition`
ne produit aucune requête valide, le résultat est `None` (aucune requête).

P5 reste gelé : ni le classifier, ni `dispatch()`, ni `CognitiveCore` ne sont
touchés ou contournés. Les autres intentions passent par leurs chemins
existants inchangés.
"""

from __future__ import annotations

from typing import Any, Optional

from core.knowledge.retrieval import (
    KnowledgeResult,
    query_from_cognition,
    retrieve,
)


def answer_search(store: Any, output: Any,
                  now: Any = None) -> Optional[KnowledgeResult]:
    """Répond à un NEED_SEARCH via O2 local, ou `None` si non traitable."""
    try:
        query = query_from_cognition(output)
    except Exception:
        return None
    if query is None:
        return None
    try:
        return retrieve(store, query, now=now)
    except Exception:
        return None
