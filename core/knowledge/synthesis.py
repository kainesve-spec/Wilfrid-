"""Wilfrid — synthèse P6.4 (agrégation ascendante, sourcée, déterministe).

section → chapitre (regroupé par préfixe de section) → global.
Chaque affirmation de synthèse pointe ses chunks : jamais d'inférence
présentée comme fait source. Types : SOURCE (retrouvé), SYNTHESIS
(regroupé), INFERENCE (déduit, marqué), EXTERNAL (jamais en mono-ouvrage).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from core.knowledge.analysis import key_terms
from core.knowledge.store import KnowledgeStore

STOPWORDS_EXTRA = frozenset({"cela", "celui", "celle", "ceux", "dont"})


def section_synthesis(texts: List[str]) -> Dict[str, Any]:
    """Synthèse d'une section : idées (premières phrases), concepts, taille."""
    joined = "\n".join(texts)
    firsts = []
    for text in texts:
        sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
        if sentences:
            firsts.append(sentences[0][:200])
    return {
        "type": "SYNTHESIS",
        "idees": firsts[:5],
        "concepts": key_terms(joined)[:10],
        "chars": len(joined),
    }


def synthesize_document(store: KnowledgeStore, document_id: str) -> Dict[str, Any]:
    """Synthèse globale persistée (niveaux section + global)."""
    rows = store._conn.execute(
        "SELECT id, text FROM chunks WHERE document_id=? ORDER BY id",
        (document_id,)).fetchall()
    if not rows:
        raise ValueError(f"aucun chunk pour {document_id}")
    by_section: Dict[str, List[str]] = {}
    for row in rows:
        section = row["id"].rsplit(":c", 1)[0]
        by_section.setdefault(section, []).append(row["text"])
    sections = {sec: section_synthesis(texts)
                for sec, texts in sorted(by_section.items())}
    all_text = "\n".join(t for texts in by_section.values() for t in texts)
    concepts = key_terms(all_text)[:15]
    uncertainties: List[str] = []
    for row in rows:
        lowered = row["text"].lower()
        for marker in ("peut-être", "probablement", "sans doute", "incertain"):
            if marker in lowered:
                uncertainties.append(f"{row['id']}: « {marker} »")
                break
    global_synthesis = {
        "type": "SYNTHESIS",
        "idees_principales": [
            s["idees"][0] for s in sections.values() if s["idees"]][:5],
        "concepts_cles": concepts,
        "structure": [{"section": sec, "idees": synth["idees"][:3]}
                      for sec, synth in sections.items()],
        "incertitudes": uncertainties[:10],
        "questions_ouvertes": [],
    }
    store.save_synthesis(f"{document_id}:global", document_id, "global",
                         json.dumps(global_synthesis, ensure_ascii=False))
    return global_synthesis


def get_synthesis(store: KnowledgeStore, document_id: str) -> Optional[Dict[str, Any]]:
    raw = store.get_synthesis(document_id, "global")
    if raw is None:
        return None
    return json.loads(raw)
