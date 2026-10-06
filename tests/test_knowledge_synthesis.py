"""Tests P6.4 — synthèse structurée, typée, persistée, sans invention."""

from __future__ import annotations

import pytest

from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex
from core.knowledge.synthesis import get_synthesis, synthesize_document

TEXT = ("Wilfrid est un assistant local et discret. "
        "Il écoute le mot éveil en continu. "
        "Peut-être parlera-t-il plusieurs langues un jour. " * 60)


def _db():
    store = KnowledgeStore(":memory:")
    jobs = JobManager(store)
    store.upsert_document("doc-s", sha256_hex(b"s"))
    jobs.create("js", "ingest")
    index_document_sections(store, jobs, "js", "doc-s", [(1, TEXT)])
    return store


def test_synthesis_structure_and_types():
    store = _db()
    try:
        result = synthesize_document(store, "doc-s")
        assert result["type"] == "SYNTHESIS"
        assert result["idees_principales"] and result["concepts_cles"]
        assert isinstance(result["structure"], list)
        assert isinstance(result["incertitudes"], list)
        assert "questions_ouvertes" in result
        reread = get_synthesis(store, "doc-s")
        assert reread is not None
        assert reread["concepts_cles"] == result["concepts_cles"]
    finally:
        store.close()


def test_synthesis_empty_document_refused():
    store = KnowledgeStore(":memory:")
    try:
        store.upsert_document("doc-e", sha256_hex(b"e"))
        with pytest.raises(ValueError):
            synthesize_document(store, "doc-e")
        assert get_synthesis(store, "doc-e") is None
    finally:
        store.close()


def test_inference_never_presented_as_source():
    store = _db()
    try:
        result = synthesize_document(store, "doc-s")
        assert result["type"] != "SOURCE"
        for idea in result["idees_principales"]:
            assert isinstance(idea, str) and idea
    finally:
        store.close()
