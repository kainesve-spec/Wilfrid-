"""Tests P5 — décideur : cohérence, bornes, sans effets."""

from __future__ import annotations

from core.cognitive.classifier import classify
from core.cognitive.decider import decide
from core.cognitive.input import build_input
from core.cognitive.types import (
    CognitiveOutput,
    CognitiveParams,
    IntentKind,
)


def _decide_for(text: str) -> CognitiveOutput:
    inp = build_input(text=text, session_id="s", context_snapshot=[],
                      timestamp=1.0, source="test")
    return decide(classify(inp.text), inp)


def test_missing_forces_clarify():
    out = decide(CognitiveOutput(IntentKind.NEED_ACTION,
                                 CognitiveParams(action="rappel"),
                                 0.85, ["objet"]),
                 build_input(text="x", session_id="s", context_snapshot=[],
                             timestamp=1.0, source="t"))
    assert out.kind == IntentKind.CLARIFY
    assert out.missing == ["objet"]


def test_confidence_clamped():
    out = decide(CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                                 99.0, []),
                 build_input(text="x", session_id="s", context_snapshot=[],
                             timestamp=1.0, source="t"))
    assert out.confidence == 1.0
    out2 = decide(CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                                  float("nan"), []),
                  build_input(text="x", session_id="s", context_snapshot=[],
                              timestamp=1.0, source="t"))
    assert out2.confidence == 0.0


def test_payload_bounded():
    long_params = CognitiveParams(question="q" * 500,
                                  etapes=["e" * 300 for _ in range(20)])
    out = decide(CognitiveOutput(IntentKind.NEED_SEARCH, long_params,
                                 0.8, []),
                 build_input(text="x", session_id="s", context_snapshot=[],
                             timestamp=1.0, source="t"))
    assert len(out.params.question) <= 200
    assert len(out.params.etapes) <= 8
    assert all(len(e) <= 80 for e in out.params.etapes)


def test_end_to_end_kinds_preserved():
    assert _decide_for("Bonjour Wilfrid").kind == IntentKind.DIRECT
    assert _decide_for("Ouvre YouTube").kind == IntentKind.NEED_ACTION
    assert _decide_for("").kind == IntentKind.CLARIFY
