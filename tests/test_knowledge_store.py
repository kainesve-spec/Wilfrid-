"""Tests P6.1 — SQLite (:memory:), schéma, transactions, FTS5, hash."""

from __future__ import annotations

import pytest

from core.knowledge.store import KnowledgeStore, sha256_hex


def test_create_and_schema():
    store = KnowledgeStore(":memory:")
    try:
        tables = {r[0] for r in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for expected in ("sources", "documents", "sections", "chunks",
                         "analyses", "syntheses", "provenance", "citations",
                         "jobs", "permissions", "whitelist", "access_log"):
            assert expected in tables, expected
    finally:
        store.close()


def test_document_idempotent_and_hash_unique():
    store = KnowledgeStore(":memory:")
    try:
        digest = sha256_hex(b"contenu")
        store.upsert_document("d1", digest, title="T")
        store.upsert_document("d1", digest, title="T")  # idempotent
        with pytest.raises(Exception):
            store.upsert_document("d2", digest, title="T2")  # hash unique
        assert store.document_status("d1") == "ACQUIRED"
        store.set_document_status("d1", "DONE")
        assert store.document_status("d1") == "DONE"
        with pytest.raises(ValueError):
            store.set_document_status("nope", "DONE")
    finally:
        store.close()


def test_chunks_fts_search():
    store = KnowledgeStore(":memory:")
    try:
        store.upsert_document("d1", sha256_hex(b"x"))
        store.add_chunk("d1:0", "d1", 0, "wilfrid moteur cognitif local")
        store.add_chunk("d1:1", "d1", 1, "tout autre sujet ici")
        hits = store.search_chunks("cognitif")
        assert [h["id"] for h in hits] == ["d1:0"]
        assert store.search_chunks("absentxyz") == []
    finally:
        store.close()


def test_permissions_whitelist_persist():
    store = KnowledgeStore(":memory:")
    try:
        store.save_permission("SOURCE_ACCESS", True, scope="s", version=2,
                              reason="t")
        loaded = store.load_permission("SOURCE_ACCESS")
        assert loaded is not None and loaded["enabled"] == 1
        assert loaded["version"] == 2
        store.save_whitelist("example.com", "active")
        assert store.load_whitelist("example.com") == "active"
        assert store.load_whitelist("nope.example") is None
    finally:
        store.close()


def test_jobs_persist_and_reopen(tmp_path=None):
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp(prefix="p61db_"))
    try:
        db = tmp / "k.db"
        first = KnowledgeStore(db)
        first.create_job("j1", "ingest", document_id=None)
        first.set_job_status("j1", "PARSING", ["downloaded"])
        first.close()
        second = KnowledgeStore(db)
        try:
            job = second.get_job("j1")
            assert job is not None and job["status"] == "PARSING"
            assert job["completed_steps"] == ["downloaded"]
        finally:
            second.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
