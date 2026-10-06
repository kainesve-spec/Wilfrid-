"""Tests P6.5 — comparaison inter-documents : isolation, provenance séparée."""

from __future__ import annotations

from core.knowledge import compare as C
from core.knowledge.chunking import index_document_sections
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore, sha256_hex


def _db(pairs):
    store = KnowledgeStore(":memory:")
    jobs = JobManager(store)
    for doc_id, text in pairs:
        store.upsert_document(doc_id, sha256_hex(doc_id.encode()))
        jobs.create("j-" + doc_id, "ingest")
        index_document_sections(store, jobs, "j-" + doc_id, doc_id,
                                [(1, text)])
    return store


def test_paris_madrid_difference_and_isolation():
    store = _db([
        ("A", "Paris est la capitale de la France. " * 60),
        ("B", "Madrid est la capitale de l'Espagne. " * 60),
    ])
    try:
        res = C.compare(store, "A", "B")
        assert res["status"] == "COMPARED"
        assert set(res["documents"]) == {"A", "B"}
        assert res["type"] == "SYNTHESIS"
        assert all(p["document_id"] == "A" for p in res["preuves_a"])
        assert all(p["document_id"] == "B" for p in res["preuves_b"])
        # Q/R mono-document sur A : jamais de preuve de B.
        from core.knowledge import qa as QA

        answer = QA.answer(store, "A", "Quelle est la capitale de la France ?")
        assert answer["type"] == "SOURCE"
        assert all("A:" in chunk for chunk in answer["chunks"])
    finally:
        store.close()


def test_three_documents_common_themes():
    store = _db([
        ("A", "Le moteur Wilfrid écoute en continu sur le téléphone. " * 60),
        ("B", "Le moteur Wilfrid répond après détection du mot. " * 60),
        ("C", "Les bananes mûrissent dans les climats chauds. " * 60),
    ])
    try:
        res_ab = C.compare(store, "A", "B")
        assert res_ab["status"] == "COMPARED"
        assert "wilfrid" in res_ab["themes_communs"]
        res_ac = C.compare(store, "A", "C")
        assert res_ac["status"] == "COMPARED"
        assert res_ac["similarity"] <= res_ab["similarity"]
    finally:
        store.close()


def test_identical_and_disjoint_and_empty():
    store = _db([
        ("A", "Texte rigoureusement identique répété. " * 80),
        ("B", "Texte rigoureusement identique répété. " * 80),
        ("C", "Zèbres quantiques sur volcans lointains. " * 80),
    ])
    try:
        same = C.compare(store, "A", "B")
        assert same["status"] == "COMPARED"
        assert same["similarity"] == 1.0
        disjoint = C.compare(store, "A", "C")
        assert disjoint["status"] == "COMPARED"
        assert disjoint["similarity"] == 0.0
        assert disjoint["themes_communs"] == []
        store.upsert_document("E", sha256_hex(b"e"))
        empty = C.compare(store, "A", "E")
        assert empty["status"] == "INSUFFICIENT_EVIDENCE"
        unknown = C.compare(store, "A", "ZZZ")
        assert unknown["status"] == "INSUFFICIENT_EVIDENCE"
    finally:
        store.close()


def test_deterministic_tiebreak():
    store = _db([("A", "Alpha beta gamma delta. " * 100),
                 ("B", "Alpha beta gamma delta. " * 100)])
    try:
        first = C.compare(store, "A", "B")
        second = C.compare(store, "A", "B")
        assert first == second
    finally:
        store.close()
