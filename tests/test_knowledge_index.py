"""Tests P6.3 — indexation FTS5, persistance, reprise, idempotence."""

from __future__ import annotations

import pytest

from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex


def _doc(store, doc_id="doc-1", text=None):
    store.upsert_document(doc_id, sha256_hex(doc_id.encode()))
    return doc_id


def test_index_search_french_unicode():
    store = KnowledgeStore(":memory:")
    try:
        jobs = JobManager(store)
        _doc(store)
        jobs.create("j1", "ingest")
        jobs.transition("j1", "DOWNLOADING")
        jobs.transition("j1", "PARSING")
        jobs.transition("j1", "CHUNKING")
        res = index_document_sections(
            store, jobs, "j1", "doc-1",
            [(1, "Le cœur du réacteur chauffe. " * 100)])
        assert res["chunks"] >= 1
        hits = store.search_chunks("cœur")
        assert [h["id"] for h in hits] == ["doc-1:s1:c0"]
        assert store.search_chunks("inexistantzzz") == []
    finally:
        store.close()


def test_persistence_reopen(tmp_path=None):
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="p63db_"))
    try:
        db = tmp / "k.db"
        first = KnowledgeStore(db)
        jobs = JobManager(first)
        _doc(first)
        jobs.create("j1", "ingest")
        index_document_sections(
            first, jobs, "j1", "doc-1", [(1, "Texte naïve été. " * 100)])
        first.close()
        second = KnowledgeStore(db)
        try:
            assert [h["id"] for h in
                    second.search_chunks("naïve")] == ["doc-1:s1:c0"]
        finally:
            second.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_resume_no_double_count():
    store = KnowledgeStore(":memory:")
    try:
        jobs = JobManager(store)
        _doc(store)
        jobs.create("j1", "ingest")
        secs = [(1, "Alpha. " * 300), (2, "Bêta. " * 300)]
        first = index_document_sections(store, jobs, "j1", "doc-1", secs)
        # Interruption simulée : reprise complète identique.
        second = index_document_sections(store, jobs, "j1", "doc-1", secs)
        assert second == {"chunks": 0, "sections_indexed": 0}
        rows = store._conn.execute(
            "SELECT count(*) FROM chunks").fetchone()[0]
        assert rows == first["chunks"] > 0
        assert store.search_chunks("Alpha") and store.search_chunks("Bêta")
    finally:
        store.close()


def test_partial_state_never_done():
    store = KnowledgeStore(":memory:")
    try:
        jobs = JobManager(store)
        jobs.create("j1", "ingest")
        assert store.get_job("j1")["status"] == "QUEUED"
        with pytest.raises(Exception):
            jobs.transition("j1", "DONE")
    finally:
        store.close()
