"""Tests P6.6 — concurrence SQLite : threads, reprise, idempotence."""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex


def _tmp():
    tmp = Path(tempfile.mkdtemp(prefix="p66c_"))
    return tmp


def _clean(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


def test_concurrent_index_no_double():
    tmp = _tmp()
    try:
        db = tmp / "k.db"
        errors = []

        def worker(i):
            try:
                store = KnowledgeStore(db)
                try:
                    jobs = JobManager(store)
                    did = "doc-%d" % i
                    store.upsert_document(did, sha256_hex(did.encode()))
                    jobs.create("j" + did, "ingest")
                    index_document_sections(
                        store, jobs, "j" + did, did,
                        [(1, "Contenu test numéro %d. " % i * 100)])
                finally:
                    store.close()
            except Exception as exc:  # noqa: BLE001 - collectée, pas masquée
                errors.append((i, type(exc).__name__, str(exc)[:100]))

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        assert not any(t.is_alive() for t in threads)
        assert errors == [], errors
        store = KnowledgeStore(db)
        try:
            n_docs = store._conn.execute(
                "SELECT count(*) FROM documents").fetchone()[0]
            assert n_docs == 8
            for i in range(8):
                prov = store.chunk_provenance("doc-%d:s1:c0" % i)
                assert prov is not None and prov["document_id"] == "doc-%d" % i
        finally:
            store.close()
    finally:
        _clean(tmp)


def test_resume_after_partial_no_recount():
    tmp = _tmp()
    try:
        db = tmp / "k.db"
        store = KnowledgeStore(db)
        try:
            jobs = JobManager(store)
            store.upsert_document("r", sha256_hex(b"r"))
            jobs.create("jr", "ingest")
            secs = [(1, "Alpha. " * 200), (2, "Bêta. " * 200)]
            first = index_document_sections(store, jobs, "jr", "r", secs)
            # Crash simulé : nouvelle instance, même job, mêmes sections.
            jobs2 = JobManager(store)
            second = index_document_sections(store, jobs2, "jr", "r", secs)
            assert second == {"chunks": 0, "sections_indexed": 0}
            n = store._conn.execute(
                "SELECT count(*) FROM chunks WHERE document_id='r'"
            ).fetchone()[0]
            assert n == first["chunks"] > 0
            assert store.search_chunks("Alpha") and store.search_chunks("Bêta")
        finally:
            store.close()
    finally:
        _clean(tmp)


def test_no_premature_done_without_persistence():
    store = KnowledgeStore(":memory:")
    try:
        jobs = JobManager(store)
        jobs.create("jn", "ingest")
        # Un job sans aucune écriture persistée ne peut pas être DONE.
        assert store.get_job("jn")["status"] == "QUEUED"
        n = store._conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        assert n == 0
    finally:
        store.close()
