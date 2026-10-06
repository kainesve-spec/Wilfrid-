"""Tests P6.4 — analyse déterministe, sourcée, persistée."""

from __future__ import annotations

from core.knowledge.analysis import analyze_chunk, analyze_document
from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex

TEXT = ("Wilfrid est un assistant local. Il écoute le mot éveil. "
        "Peut-être comprendra-t-il un jour le langage? " * 40)


def _db(doc_id="doc-a"):
    store = KnowledgeStore(":memory:")
    jobs = JobManager(store)
    store.upsert_document(doc_id, sha256_hex(doc_id.encode()))
    jobs.create("ja", "ingest")
    index_document_sections(store, jobs, "ja", doc_id, [(1, TEXT)])
    return store


def test_analyze_deterministic_with_provenance():
    first = analyze_chunk("c1", TEXT)
    second = analyze_chunk("c1", TEXT)
    assert first == second
    assert first["claims"] and first["concepts"]
    assert all(c["chunk_id"] == "c1" for c in first["claims"])
    assert all(c["chunk_id"] == "c1" for c in first["concepts"])
    assert any(q["text"].endswith("?") for q in first["questions"])
    assert first["uncertainties"]  # "peut-être" détecté


def test_analyze_document_persists_idempotent():
    store = _db()
    try:
        total = analyze_document(store, "doc-a")
        assert total["chunks"] >= 1 and total["claims"] >= 1
        rows = store._conn.execute(
            "SELECT count(*) FROM analyses").fetchone()[0]
        total2 = analyze_document(store, "doc-a")
        rows2 = store._conn.execute(
            "SELECT count(*) FROM analyses").fetchone()[0]
        assert rows == rows2 and total == total2  # idempotent
    finally:
        store.close()


def test_no_semantic_overclaim():
    res = analyze_chunk("c9", "Texte neutre sans marqueur. Phrase simple.")
    assert res["uncertainties"] == []
    assert res["questions"] == []
