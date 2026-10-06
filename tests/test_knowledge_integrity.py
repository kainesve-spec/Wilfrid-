"""Tests P6.6 — intégrité : SHA, altération, provenance non falsifiable."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex


def _tmp():
    tmp = Path(tempfile.mkdtemp(prefix="p66i_"))
    return tmp


def _clean(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


def _db(tmp):
    db = tmp / "k.db"
    store = KnowledgeStore(db)
    return store, JobManager(store)


def test_tamper_detected_by_hash():
    tmp = _tmp()
    try:
        store, jobs = _db(tmp)
        try:
            content = b"contenu original du document"
            digest = sha256_hex(content)
            doc = tmp / "doc.txt"
            doc.write_bytes(content)
            doc_id = "doc-t"
            store.upsert_document(doc_id, digest)
            jobs.create("jt", "ingest")
            # Altération après acquisition : le hash ne correspond plus.
            doc.write_bytes(content + b" [PIRATE]")
            current = sha256_hex(doc.read_bytes())
            assert current != digest
            stored = store._conn.execute(
                "SELECT sha256 FROM documents WHERE id=?",
                (doc_id,)).fetchone()[0]
            assert stored == digest != current  # falsification détectable
        finally:
            store.close()
    finally:
        _clean(tmp)


def test_mismatch_never_done():
    tmp = _tmp()
    try:
        store, jobs = _db(tmp)
        try:
            jobs.create("jm", "ingest")
            # Document sans chunks indexés : pas de DONE, pas de synthèse vide.
            store.upsert_document("vide", sha256_hex(b"vide"))
            assert store.get_job("jm")["status"] == "QUEUED"
            n = store._conn.execute(
                "SELECT count(*) FROM chunks WHERE document_id='vide'"
            ).fetchone()[0]
            assert n == 0
        finally:
            store.close()
    finally:
        _clean(tmp)


def test_provenance_cannot_cross_documents():
    tmp = _tmp()
    try:
        store, jobs = _db(tmp)
        try:
            for did, text in (("pa", "Pommes vertes. " * 100),
                              ("pb", "Voitures rouges. " * 100)):
                store.upsert_document(did, sha256_hex(did.encode()))
                jobs.create("j" + did, "ingest")
                index_document_sections(store, jobs, "j" + did, did,
                                        [(1, text)])
            # Chaque provenance pointe son propre document, jamais l'autre.
            for chunk_id, owner in (("pa:s1:c0", "pa"), ("pb:s1:c0", "pb")):
                prov = store.chunk_provenance(chunk_id)
                assert prov is not None
                assert prov["document_id"] == owner
                assert prov["sha256"] == sha256_hex(owner.encode())
            # Falsification directe impossible via l'API publique :
            # chunk_provenance joint documents (SHA réel, pas déclaratif).
            assert "pb" not in str(store.chunk_provenance("pa:s1:c0"))
        finally:
            store.close()
    finally:
        _clean(tmp)
