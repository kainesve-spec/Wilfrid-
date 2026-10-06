"""Tests P6.4 — Q/R extractif : preuves ou INSUFFICIENT_EVIDENCE."""

from __future__ import annotations

from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge import qa as QA
from core.knowledge.store import KnowledgeStore, sha256_hex

TEXT = ("Wilfrid est un assistant local et discret. "
        "Il écoute le mot éveil en continu dans le salon. "
        "Le modèle reste petit pour tenir sur un téléphone. " * 80)


def _db():
    store = KnowledgeStore(":memory:")
    jobs = JobManager(store)
    store.upsert_document("doc-q", sha256_hex(b"q"))
    jobs.create("jq", "ingest")
    index_document_sections(store, jobs, "jq", "doc-q", [(1, TEXT)])
    return store


def test_answer_source_with_provenance():
    store = _db()
    try:
        res = QA.answer(store, "doc-q", "Où écoute Wilfrid en continu ?")
        assert res["type"] == "SOURCE"
        assert res["chunks"] and res["provenance"]
        assert res["provenance"][0]["document_id"] == "doc-q"
        assert 0.0 < res["confidence"] <= 1.0
        assert "salon" in res["answer"]
    finally:
        store.close()


def test_insufficient_evidence_never_invents():
    store = _db()
    try:
        for question in ["Quelle est la capitale du Pérou ?",
                         "zzzqqq xxxwww",
                         ""]:
            res = QA.answer(store, "doc-q", question)
            assert res["type"] == "INSUFFICIENT_EVIDENCE"
            assert res["answer"] == "" and res["chunks"] == []
            assert res["confidence"] == 0.0
    finally:
        store.close()


def test_synthesis_variant_labeled():
    store = _db()
    try:
        from core.knowledge.synthesis import synthesize_document

        synthesize_document(store, "doc-q")
        res = QA.answer_with_synthesis(store, "doc-q",
                                       "Quelle est l'idée centrale ?")
        assert res["type"] in ("SYNTHESIS", "SOURCE")
        if res["type"] == "SYNTHESIS":
            assert res["provenance"][0]["document_id"] == "doc-q"
    finally:
        store.close()


def test_cross_document_isolation():
    store = KnowledgeStore(":memory:")
    try:
        jobs = JobManager(store)
        for doc_id, text in (("d1", "Pommes vertes ici. " * 100),
                             ("d2", "Voitures rouges là. " * 100)):
            store.upsert_document(doc_id, sha256_hex(doc_id.encode()))
            jobs.create("j" + doc_id, "ingest")
            index_document_sections(store, jobs, "j" + doc_id, doc_id,
                                    [(1, text)])
        res = QA.answer(store, "d2", "Parle-moi des voitures rouges")
        assert all("d2:" in chunk for chunk in res["chunks"])
    finally:
        store.close()
