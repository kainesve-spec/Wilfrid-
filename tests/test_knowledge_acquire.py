"""Tests P6.2 — acquire_and_parse : checkpoints, reprise, déduplication."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from core.knowledge.acquire import acquire_and_parse
from core.knowledge.jobs import JobManager
from core.knowledge.permissions import PermissionRegistry
from core.knowledge.store import KnowledgeStore
from core.knowledge.whitelist import Whitelist

CONTENT = b"Wilfrid acquisition test. " * 50
CONTENT_SHA = hashlib.sha256(CONTENT).hexdigest()


class _FakeDownload:
    """Double du downloader : aucun réseau, scénarios contrôlés."""

    def __init__(self, tmp_payload=b""):
        self.tmp_payload = tmp_payload
        self.calls = []

    def __call__(self, url, dest_dir, filename, **kw):
        from core.knowledge import downloader as DL

        self.calls.append(url)
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / (filename + ".part")
        target.write_bytes(self.tmp_payload or CONTENT)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        final = dest / filename
        target.replace(final)
        return DL.DownloadResult(
            ok=True, path=final, sha256=digest, size=len(CONTENT),
            mime_declared="text/plain", url_final=url)


def _env():
    reg = PermissionRegistry()
    reg.enable("DOCUMENT_DOWNLOAD", reason="t")
    wl = Whitelist()
    wl.add("example.com")
    return reg, wl


def _checkpoints(store, job_id):
    job = store.get_job(job_id)
    assert job is not None
    return job["completed_steps"]


def test_acquire_parse_checkpoints():
    import core.knowledge.acquire as acquire_mod

    tmp = Path(tempfile.mkdtemp(prefix="p62a_"))
    try:
        store = KnowledgeStore(":memory:")
        jobs = JobManager(store)
        reg, wl = _env()
        jobs.create("j1", "ingest")
        fake = _FakeDownload()
        real = acquire_mod._download.download
        acquire_mod._download.download = fake
        try:
            res = acquire_and_parse(
                "j1", "https://example.com/doc.txt", "doc.txt",
                jobs=jobs, store=store,
                check_permission=reg.check, check_whitelist=wl.check_url,
                base_dir=tmp)
        finally:
            acquire_mod._download.download = real
        assert res["ok"] is True and res["stage"] == "parsed"
        assert res["sha256"] == CONTENT_SHA
        assert _checkpoints(store, "j1") == ["downloaded",
                                             f"parsed-{res['doc_id']}"]
        assert store.document_status(res["doc_id"]) == "PARSED"
        # Pas de DONE prématuré : le job reste en PARSING (P6.3 continue).
        assert store.get_job("j1")["status"] == "PARSING"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_acquire_failure_visible_and_resumable():
    import core.knowledge.acquire as acquire_mod

    tmp = Path(tempfile.mkdtemp(prefix="p62a_"))
    try:
        store = KnowledgeStore(":memory:")
        jobs = JobManager(store)
        reg, wl = _env()
        jobs.create("j1", "ingest")
        real = acquire_mod._download.download

        def _fail(*a, **k):
            from core.knowledge import downloader as DL

            return DL.DownloadResult(ok=False, error="FAIL flux")

        acquire_mod._download.download = _fail
        try:
            res = acquire_and_parse(
                "j1", "https://example.com/doc.txt", "doc.txt",
                jobs=jobs, store=store,
                check_permission=reg.check, check_whitelist=wl.check_url,
                base_dir=tmp)
        finally:
            acquire_mod._download.download = real
        assert res["ok"] is False and res["stage"] == "download"
        assert store.get_job("j1")["status"] == "FAILED"
        # Reprise : le job repart, les checkpoints restent cohérents.
        jobs.resume("j1")
        assert store.get_job("j1")["status"] == "QUEUED"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sha_dedup_across_urls():
    import core.knowledge.acquire as acquire_mod

    tmp = Path(tempfile.mkdtemp(prefix="p62a_"))
    try:
        store = KnowledgeStore(":memory:")
        jobs = JobManager(store)
        reg, wl = _env()
        real = acquire_mod._download.download
        fake = _FakeDownload()
        acquire_mod._download.download = fake
        try:
            jobs.create("j1", "ingest")
            r1 = acquire_and_parse(
                "j1", "https://example.com/a.txt", "a.txt",
                jobs=jobs, store=store,
                check_permission=reg.check, check_whitelist=wl.check_url,
                base_dir=tmp)
            jobs.create("j2", "ingest")
            r2 = acquire_and_parse(
                "j2", "https://example.com/b.txt", "b.txt",
                jobs=jobs, store=store,
                check_permission=reg.check, check_whitelist=wl.check_url,
                base_dir=tmp)
        finally:
            acquire_mod._download.download = real
        assert r1["ok"] and r2["ok"]
        assert r1["doc_id"] == r2["doc_id"]  # même SHA → même document
        corpus = list((tmp / "corpus").glob("*"))
        assert len(corpus) == 1  # un seul fichier physique
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
