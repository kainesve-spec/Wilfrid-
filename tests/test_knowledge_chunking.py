"""Tests P6.3 — chunking déterministe, borné, IDs stables."""

from __future__ import annotations

from core.knowledge.chunking import (
    chunk_document,
    chunk_section_text,
    split_sentences,
)


def _text(n_sentences=200):
    return " ".join(
        f"Phrase numéro {i} avec des accents été cœur naïve."
        for i in range(n_sentences))


def test_deterministic():
    text = _text()
    assert chunk_section_text(text) == chunk_section_text(text)


def test_sizes_and_overlap():
    pieces = chunk_section_text(_text(200))
    assert len(pieces) >= 2
    for piece in pieces:
        assert len(piece.split()) <= 1200 + 130
    first, second = pieces[0].split(), pieces[1].split()
    assert first[-130:] == second[:130]  # overlap ~10-15 %


def test_section_boundaries_and_small_sections():
    out = chunk_document("doc-x", [(1, "Court."), (2, _text(200))])
    assert out[0]["chunk_id"] == "doc-x:s1:c0"
    assert out[0]["text"] == "Court."
    assert all(c["section_ordinal"] == 2 for c in out[1:])
    assert [c["chunk_id"] for c in out[1:]] == [
        f"doc-x:s2:c{i}" for i in range(len(out) - 1)]


def test_long_paragraphs_and_unicode():
    para = ("Un paragraphe très long sans ponctuation " * 300).strip()
    pieces = chunk_section_text(para)
    assert len(pieces) >= 2
    assert all(len(p.split()) <= 1200 + 130 for p in pieces)
    fr = "Voilà l'été : ça avance — « naïve » ✓."
    assert chunk_section_text(fr) == [fr]


def test_empty_and_incomplete():
    assert chunk_section_text("") == []
    assert chunk_section_text("   \n  ") == []
    assert chunk_document("doc-e", []) == []
    assert chunk_document("doc-e", [(1, ""), (2, "   ")]) == []


def test_no_sentence_cut_unnecessarily():
    sents = [f"Phrase {i} complète." for i in range(50)]
    text = " ".join(sents)
    pieces = chunk_section_text(text)
    assert len(pieces) == 1
    for sent in sents:
        assert any(sent in p for p in pieces)
