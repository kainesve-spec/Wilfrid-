"""Tests P5 — classifieur : corpus 24 cas + confiance + déterminisme."""

from __future__ import annotations

import json
from pathlib import Path

from core.cognitive.classifier import classify

CORPUS = json.loads(
    (Path(__file__).resolve().parent / "data"
     / "cognitive_corpus_v1.json").read_text(encoding="utf-8"))


def test_corpus_taxonomy_version():
    assert CORPUS["corpus_version"] == "1.0"
    assert CORPUS["taxonomy_version"] == "1.0"
    assert len(CORPUS["cases"]) == 24


def test_corpus_all_kinds():
    bad = []
    for case in CORPUS["cases"]:
        got = classify(case["text"])
        if got.kind.value != case["expected_kind"] or \
                list(got.missing) != case["expected_missing"]:
            bad.append((case["id"], case["expected_kind"], got.kind.value))
    assert bad == []


def test_each_kind_reachable():
    kinds = {classify(c["text"]).kind.value for c in CORPUS["cases"]}
    assert kinds == {"DIRECT", "CLARIFY", "PLAN", "NEED_SEARCH", "NEED_TOOL",
                     "NEED_ACTION", "REFUSE", "UNCERTAIN"}


def test_confidence_rule_based_bounded():
    for case in CORPUS["cases"]:
        got = classify(case["text"])
        assert 0.0 <= got.confidence <= 1.0
    # Ambiguïtés traitées conservativement (confiance non maximale).
    assert classify("xkzj qwx blorb").confidence < 0.5
    assert classify("").confidence >= 0.9  # vide = certainement flou


def test_determinism():
    for case in CORPUS["cases"]:
        first = classify(case["text"])
        second = classify(case["text"])
        assert (first.kind, first.confidence, list(first.missing),
                first.params) == \
               (second.kind, second.confidence, list(second.missing),
                second.params)


def test_params_are_plain_data():
    got = classify("Envoie un message à Marie")
    assert got.params.action == "envoie"
    assert got.params.objet == "message"
    assert got.params.cible == "Marie"
    assert isinstance(got.params.etapes, list)
