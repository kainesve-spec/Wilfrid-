"""Wilfrid — Q/R mono-ouvrage P6.4 (extractif, sourcé, honnête).

Pipeline : question → FTS5 → provenance → contexte borné → réponse.
Types : SOURCE (extrait direct), SYNTHESIS (synthèse persistée),
INFERENCE (marqué, jamais présenté comme source), EXTERNAL (jamais
produit ici). Preuves insuffisantes → INSUFFICIENT_EVIDENCE, jamais
d'invention. Confiance heuristique documentée (recouvrement), pas de
probabilité calibrée.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.knowledge.store import KnowledgeStore

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüçœæ-]{3,}")
_STOPWORDS = frozenset(
    "le la les de des du un une et est sont dans pour par sur avec ce "
    "cette ces il ils elle elles nous vous je tu on ne pas plus tout tous "
    "toute toutes comme mais ou donc car ni que qui quoi dont the and of "
    "to in is are was were for on with that this these those it its".split())


def _keywords(question: str) -> List[str]:
    words = _WORD_RE.findall(question.lower())
    seen, out = set(), []
    for word in words:
        if word not in _STOPWORDS and word not in seen:
            seen.add(word)
            out.append(word)
    return out


def _overlap(a: List[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for word in a if word in lowered)


def answer(store: KnowledgeStore, document_id: str, question: str,
           top_k: int = 3) -> Dict[str, Any]:
    """Répond depuis un ouvrage. Jamais d'invention hors preuves."""
    keywords = _keywords(question)
    if not keywords:
        return _insufficient(document_id, question, "question-vide")
    # Termes cités : la ponctuation hostile (tirets, quotes) ne peut pas
    # détourner la syntaxe FTS ; le store reste garde-fou final.
    query = " OR ".join(f'"{term}"' for term in keywords[:8])
    try:
        hits = store.search_chunks_in_doc(query, document_id,
                                          limit=top_k * 2)
    except Exception:
        hits = []
    if not hits:
        return _insufficient(document_id, question, "aucun-passage")
    hits = hits[:top_k]
    scored = sorted(
        ((_overlap(keywords, h["text"]), h) for h in hits),
        key=lambda pair: pair[0], reverse=True)
    best_overlap, best = scored[0]
    if best_overlap == 0:
        return _insufficient(document_id, question, "recouvrement-nul")
    provenances = []
    for _score, hit in scored:
        prov = store.chunk_provenance(hit["id"])
        if prov is not None:
            provenances.append({
                "chunk_id": hit["id"],
                "location": prov.get("location", ""),
                "document_id": prov.get("document_id", ""),
            })
    confidence = round(min(0.95, 0.35 + 0.15 * best_overlap), 2)
    excerpt = best["text"][:400]
    return {
        "answer": excerpt,
        "type": "SOURCE",
        "chunks": [h["id"] for _, h in scored],
        "provenance": provenances,
        "confidence": confidence,
        "question": question,
        "document_id": document_id,
    }


def _insufficient(document_id: str, question: str,
                  reason: str) -> Dict[str, Any]:
    return {
        "answer": "",
        "type": "INSUFFICIENT_EVIDENCE",
        "chunks": [],
        "provenance": [],
        "confidence": 0.0,
        "question": question,
        "document_id": document_id,
        "reason": reason,
    }


def answer_with_synthesis(store: KnowledgeStore, document_id: str,
                          question: str) -> Dict[str, Any]:
    """Variante SYNTHESIS : répond depuis la synthèse globale persistée."""
    from core.knowledge.synthesis import get_synthesis

    lowered = question.lower()
    wants_overview = any(word in lowered for word in (
        "idée centrale", "idées principales", "résumé", "sujet",
        "de quoi parle", "about"))
    synthesis = get_synthesis(store, document_id)
    if synthesis is None or not wants_overview:
        return answer(store, document_id, question)
    ideas = synthesis.get("idees_principales", [])[:3]
    return {
        "answer": " ; ".join(ideas),
        "type": "SYNTHESIS",
        "chunks": [],
        "provenance": [{
            "chunk_id": "",
            "location": "",
            "document_id": document_id,
        }],
        "confidence": 0.6,
        "question": question,
        "document_id": document_id,
    }
