"""Wilfrid — comparaison inter-documents P6.5 (lexicale, sourcée, honnête).

Documents explicitement sélectionnés. Chaque affirmation remonte à
doc A → chunk(s) A et/ou doc B → chunk(s) B : JAMAIS de provenance
croisée. Preuves insuffisantes → INSUFFICIENT_EVIDENCE, pas de
conclusion inventée. Pas de sémantique avancée prétendue : recoupement
lexical déterministe (Jaccard sur termes, tie-break stable).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.knowledge.store import KnowledgeStore

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüçœæ-]{4,}")
_STOPWORDS = frozenset(
    "avec dans pour sont cette comme tout tous toute toutes entre donc "
    "the and for with that this from have were what when which their "
    "will would there been more other than then them these those".split())


def _terms(text: str) -> List[str]:
    seen, out = set(), []
    for word in _WORD_RE.findall(text.lower()):
        if word not in _STOPWORDS and word not in seen:
            seen.add(word)
            out.append(word)
    return out


def _jaccard(left: List[str], right: List[str]) -> float:
    set_left, set_right = set(left), set(right)
    if not set_left or not set_right:
        return 0.0
    return len(set_left & set_right) / len(set_left | set_right)


def _document_terms(store: KnowledgeStore, document_id: str,
                    limit_chunks: int = 50) -> List[str]:
    terms: List[str] = []
    for row in store.document_chunks(document_id, limit=limit_chunks):
        for term in _terms(row["text"]):
            if term not in terms:
                terms.append(term)
    return terms


def _evidence(store: KnowledgeStore, document_id: str,
              terms: List[str], limit: int = 3) -> List[Dict[str, Any]]:
    query = " OR ".join(terms[:8])
    try:
        hits = store.search_chunks_in_doc(query, document_id, limit=limit)
    except Exception:
        return []
    out = []
    for hit in hits:
        prov = store.chunk_provenance(hit["id"])
        out.append({
            "chunk_id": hit["id"],
            "document_id": document_id,
            "location": (prov or {}).get("location", ""),
            "excerpt": hit["text"][:200],
        })
    return out


def compare(store: KnowledgeStore, doc_a: str, doc_b: str) -> Dict[str, Any]:
    """Compare deux ouvrages : similitudes, différences, thèmes, preuves séparées."""
    for doc_id in (doc_a, doc_b):
        if store.document_status(doc_id) is None:
            return {"status": "INSUFFICIENT_EVIDENCE",
                    "reason": f"document inconnu: {doc_id}",
                    "documents": [doc_a, doc_b]}
    terms_a = _document_terms(store, doc_a)
    terms_b = _document_terms(store, doc_b)
    if not terms_a or not terms_b:
        return {"status": "INSUFFICIENT_EVIDENCE",
                "reason": "vocabulaire insuffisant",
                "documents": [doc_a, doc_b]}
    common = [t for t in terms_a if t in set(terms_b)]
    only_a = [t for t in terms_a if t not in set(terms_b)][:10]
    only_b = [t for t in terms_b if t not in set(terms_a)][:10]
    similarity = round(_jaccard(terms_a, terms_b), 4)
    return {
        "status": "COMPARED",
        "documents": [doc_a, doc_b],
        "similarity": similarity,
        "themes_communs": common[:15],
        "specifique_a": only_a,
        "specifique_b": only_b,
        "preuves_a": _evidence(store, doc_a, common),
        "preuves_b": _evidence(store, doc_b, common),
        "type": "SYNTHESIS",
    }
