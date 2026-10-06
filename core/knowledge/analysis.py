"""Wilfrid — analyse P6.4 (heuristique à règles, déterministe, documentée).

Ne prétend pas comprendre sémantiquement : extrait claims (phrases
matrices), concepts (termes fréquents non vides), relations de
co-occurrence, questions (phrases interrogatives), incertitudes
(marqueurs explicites). Chaque élément cite ses chunks. Persisté en
`analyses` (UNIQUE chunk+kind → idempotent). Hiérarchie chunk→section→
ouvrage via les IDs stables P6.3.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List

from core.knowledge.store import KnowledgeStore

_STOPWORDS = frozenset("""
le la les de des du un une et est sont dans pour par sur avec ce cette ces
il ils elle elles nous vous je tu on ne pas plus tout tous toute toutes
comme mais ou où donc car ni que qui quoi dont où dontlede the and of to in
is are was were for on with that this these those it its as at by from or
an a de la el los las un una y en que se del al lo como más pero sus este
""".split())

_UNCERTAIN_MARKERS = ("peut-être", "peut être", "probablement", "sans doute",
                      "il semble", "on dirait", "incertain", "doute",
                      "maybe", "probably", "uncertain", "seems")

_CLAIM_RE = re.compile(r"[^.!?…\n]+[.!?…]")


def key_terms(text: str, top_n: int = 12) -> List[str]:
    """Termes fréquents hors mots vides (heuristique fréquentielle)."""
    words = re.findall(r"[a-zàâäéèêëîïôöùûüçœæ-]{3,}", text.lower())
    counts = Counter(w for w in words if w not in _STOPWORDS)
    return [w for w, _ in counts.most_common(top_n)]


def split_claims(text: str) -> List[str]:
    return [c.strip() for c in _CLAIM_RE.findall(text) if c.strip()]


def uncertainties_in(text: str) -> List[str]:
    lowered = text.lower()
    return [m for m in _UNCERTAIN_MARKERS if m in lowered]


def questions_in(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=\?)\s+", text) if s.strip().endswith("?")]


def cooccurring_pairs(terms: List[str], text: str) -> List[List[str]]:
    lowered = text.lower()
    present = [t for t in terms if t in lowered]
    return [[a, b] for i, a in enumerate(present) for b in present[i + 1:]]


def analyze_chunk(chunk_id: str, text: str) -> Dict[str, Any]:
    """Analyse d'un chunk : données + références, zéro inférence cachée."""
    terms = key_terms(text)
    return {
        "claims": [{"text": c, "chunk_id": chunk_id}
                   for c in split_claims(text)[:5]],
        "concepts": [{"term": t, "chunk_id": chunk_id} for t in terms],
        "relations": [{"a": a, "b": b, "chunk_id": chunk_id}
                      for a, b in cooccurring_pairs(terms[:8], text)[:10]],
        "questions": [{"text": q, "chunk_id": chunk_id}
                      for q in questions_in(text)],
        "uncertainties": [{"marker": m, "chunk_id": chunk_id}
                          for m in uncertainties_in(text)],
    }


def analyze_document(store: KnowledgeStore, document_id: str) -> Dict[str, Any]:
    """Analyse tous les chunks d'un ouvrage, persiste en `analyses`."""
    rows = store._conn.execute(
        "SELECT id, text FROM chunks WHERE document_id=? ORDER BY id",
        (document_id,)).fetchall()
    total = {"claims": 0, "concepts": 0, "relations": 0, "questions": 0,
             "uncertainties": 0, "chunks": 0}
    import json as _json

    for row in rows:
        result = analyze_chunk(row["id"], row["text"])
        store.save_analysis(f"{row['id']}:analysis", row["id"],
                            _json.dumps(result, ensure_ascii=False))
        for key in total:
            if key != "chunks":
                total[key] += len(result[key])
        total["chunks"] += 1
    return total
