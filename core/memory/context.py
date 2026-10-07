"""Wilfrid — contexte enrichi (session volatile + mémoire persistante).

Construit une liste de tours bornée et déterministe combinant le contexte
de session courant (prioritaire, tel quel) et des souvenirs persistants
pertinents (marqués, jamais fusionnés opaquement). Chaque élément mémorisé
conserve kind, provenance, fraîcheur, confiance et statut ; les éléments
expirés/invalidés sont exclus ; les contradictions restent visibles côte à
côte, jamais résolues. Le contexte influence la compréhension, jamais
l'autorité : aucune permission, approbation ou mandat n'est lu ni créé ici.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

MAX_CONTEXT_ITEMS = 10
MAX_CONTEXT_CHARS = 2000


def _terms(text: str) -> List[str]:
    seen: List[str] = []
    for word in str(text or "").lower().split():
        cleaned = "".join(c for c in word if c.isalnum())
        if len(cleaned) >= 3 and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _relevance(record_terms: List[str], query_terms: List[str]) -> int:
    if not query_terms:
        return 0
    return sum(1 for term in record_terms if term in query_terms)


def _record_terms(record: Any) -> List[str]:
    content = getattr(record, "content", "") or ""
    return _terms(content)


def build_context(session_turns: Any, memories: Any, *,
                  query: Any = None,
                  max_items: int = MAX_CONTEXT_ITEMS,
                  max_chars: int = MAX_CONTEXT_CHARS) -> Tuple[Dict[str, Any], ...]:
    """Assemble un contexte borné : session d'abord, souvenirs marqués ensuite.

    - `session_turns` : tours volatils `{role, text}` conservés tels quels ;
    - `memories` : `MemoryRecord` persistants ; seuls les `active` non expirés
      sont retenus, avec leurs métadonnées (kind, provenance, fraîcheur,
      confiance, statut) ;
    - tri : pertinence au `query` décroissante, puis id croissant (stable) ;
    - budget : `max_items` éléments et `max_chars` caractères au total ;
    - aucun appel réseau, subprocess, Governor, Approval ou registre.
    """
    items: List[Dict[str, Any]] = []
    if isinstance(session_turns, (tuple, list)):
        for turn in session_turns:
            if isinstance(turn, dict) and isinstance(
                    turn.get("text"), str) and turn["text"].strip():
                items.append({"role": str(turn.get("role", "user")),
                              "text": turn["text"].strip(),
                              "origin": "session"})
    query_terms = _terms(query) if isinstance(query, str) else []
    scored: List[Tuple[int, str, Any]] = []
    if memories is not None:
        try:
            candidates = list(memories)
        except TypeError:
            candidates = []
        for record in candidates:
            status = getattr(record, "status", "")
            freshness = getattr(record, "freshness", "UNKNOWN")
            if status != "active" or freshness == "EXPIRED":
                continue
            scored.append((_relevance(_record_terms(record), query_terms),
                           str(getattr(record, "id", "")), record))
    scored.sort(key=lambda item: (-item[0], item[1]))
    try:
        items_budget = max(1, min(int(max_items), MAX_CONTEXT_ITEMS))
    except (TypeError, ValueError):
        items_budget = MAX_CONTEXT_ITEMS
    try:
        chars_budget = max(1, min(int(max_chars), MAX_CONTEXT_CHARS))
    except (TypeError, ValueError):
        chars_budget = MAX_CONTEXT_CHARS
    used_chars = sum(len(str(item.get("text", ""))) for item in items)
    for _, _, record in scored:
        if len(items) >= items_budget:
            break
        text = str(getattr(record, "content", "") or "")
        if not text.strip():
            continue
        if used_chars + len(text) > chars_budget:
            continue
        items.append({
            "role": "wilfrid-memory",
            "text": text,
            "origin": "memory",
            "record_id": str(getattr(record, "id", "")),
            "kind": str(getattr(record, "kind", "")),
            "provenance": str(getattr(record, "provenance_source", "")),
            "freshness": str(getattr(record, "freshness", "UNKNOWN")),
            "status": str(getattr(record, "status", "")),
        })
        used_chars += len(text)
    return tuple(items)
