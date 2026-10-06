"""Wilfrid — chunking P6.3 (déterministe, borné, idempotent).

Découpage : phrases d'abord (jamais coupées sauf > cible), puis
paragraphes, troncature dure en dernier recours uniquement.
Cible ~800-1200 "tokens" (mot ≈ token, approximation documentée),
overlap ~10-15 %, frontières de section respectées (un chunk ne
traverse jamais deux sections). Sections plus petites que la cible :
un seul chunk. IDs stables `doc:sec:chunk` (doc contient déjà le hash).
Reprise : sections validées skippées, INSERT OR IGNORE → aucun doublon.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

TARGET_WORDS = 1000
MAX_WORDS = 1200
OVERLAP_WORDS = 130

_SENTENCE_RE = re.compile(r"[^.!?…\n]+[.!?…]+|[^\n]+$")


def split_sentences(text: str) -> List[str]:
    """Découpe en phrases (déterministe, Unicode-safe)."""
    parts = [p.strip() for p in _SENTENCE_RE.findall(text)]
    return [p for p in parts if p]


def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def chunk_words(words: List[str]) -> List[List[str]]:
    """Regroupe en chunks ≤ MAX_WORDS avec overlap (secours mot-à-mot)."""
    chunks: List[List[str]] = []
    current: List[str] = []
    for word in words:
        current.append(word)
        if len(current) >= TARGET_WORDS:
            chunks.append(current)
            keep = current[-OVERLAP_WORDS:] if len(current) > OVERLAP_WORDS else []
            current = list(keep)
    if current and (not chunks or len(current) > OVERLAP_WORDS // 2):
        chunks.append(current)
    elif current and chunks:
        chunks[-1] = chunks[-1] + current
        if len(chunks[-1]) > MAX_WORDS + OVERLAP_WORDS:
            overflow = chunks[-1][MAX_WORDS:]
            chunks[-1] = chunks[-1][:MAX_WORDS]
            chunks.append(overflow)
    return [c for c in chunks if c]


def chunk_section_text(text: str) -> List[str]:
    """Découpe une section en phrases entières si possible.

    Les phrases ne sont jamais coupées sauf si une phrase unique dépasse
    MAX_WORDS (secours mot-à-mot). Paragraphes très longs : même règle
    via les phrases qu'ils contiennent.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    sent_words = [s.split() for s in sentences]
    if sum(len(w) for w in sent_words) <= MAX_WORDS:
        joined = " ".join(sentences)
        return [joined] if joined.strip() else []
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for words in sent_words:
        if len(words) > MAX_WORDS:
            # Phrase pathologique : secours mot-à-mot pour ce segment seul.
            if current:
                chunks.append(" ".join(current))
                current, current_len = [], 0
            for piece in chunk_words(words):
                chunks.append(" ".join(piece))
            continue
        if current and current_len + len(words) > TARGET_WORDS:
            chunks.append(" ".join(current))
            tail: List[str] = []
            for word in reversed(current):
                tail.append(word)
                if len(tail) >= OVERLAP_WORDS:
                    break
            current = list(reversed(tail))
            current_len = len(current)
        current.extend(words)
        current_len += len(words)
    if current:
        if chunks and current_len <= OVERLAP_WORDS // 2:
            chunks[-1] = chunks[-1] + " " + " ".join(current)
        else:
            chunks.append(" ".join(current))
    return [c for c in chunks if c.strip()]


def chunk_id(document_id: str, section_ordinal: int, index: int) -> str:
    return f"{document_id}:s{section_ordinal}:c{index}"


def index_document_sections(store, jobs, job_id: str, document_id: str,
                            sections, locations=None) -> Dict[str, Any]:
    """Découpe + indexe + provenance, avec checkpoints P6.1 (idempotent).

    `sections` : [(ordinal, text)]. `locations` : {ordinal: page|None}
    (page absente conservée comme ""). Sections déjà checkpointées
    skippées ; ré-exécution sans doublon (INSERT OR IGNORE).
    Retourne {chunks, sections_indexed}.
    """
    locations = locations or {}
    job = store.get_job(job_id)
    done = set(job["completed_steps"]) if job else set()
    total_chunks = 0
    indexed_sections = 0
    for ordinal, text in sections:
        marker = f"chunked-s{ordinal}"
        if marker in done:
            continue
        pieces = chunk_document(document_id, [(ordinal, text)])
        for piece in pieces:
            store.add_chunk(piece["chunk_id"], document_id,
                            piece["index"], piece["text"])
            page = locations.get(ordinal)
            location = f"page {page}" if page is not None else ""
            store.add_provenance(
                f"{piece['chunk_id']}:prov",
                claim=f"chunk {piece['index']} section {ordinal}",
                chunk_id=piece["chunk_id"], document_id=document_id,
                location=location)
            total_chunks += 1
        jobs.complete_step(job_id, marker)
        indexed_sections += 1
    return {"chunks": total_chunks, "sections_indexed": indexed_sections}


def chunk_document(document_id: str,
                   sections: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    """Découpe complète : [{chunk_id, section, index, text}]. Pure et bornée."""
    out: List[Dict[str, Any]] = []
    for ordinal, text in sections:
        if not text.strip():
            continue
        for index, piece in enumerate(chunk_section_text(text)):
            out.append({
                "chunk_id": chunk_id(document_id, ordinal, index),
                "section_ordinal": ordinal,
                "index": index,
                "text": piece,
                "words": len(piece.split()),
            })
    return out
