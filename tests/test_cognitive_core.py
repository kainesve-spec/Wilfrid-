"""Tests P5 — CognitiveCore : états, déterminisme, isolation."""

from __future__ import annotations

import pytest

from core.cognitive.core import CognitiveCore, CognitiveState
from core.cognitive.types import IntentKind


def _run(text: str, **kw):
    core = CognitiveCore()
    return core.process(text=text, session_id="s", context_snapshot=[],
                        timestamp=1.0, source="test", **kw)


def test_happy_path_states():
    result = _run("Bonjour Wilfrid")
    assert result.states == ["INPUT_RECEIVED", "ANALYZING", "DECIDING",
                             "PLANNING", "READY"]
    assert result.state == CognitiveState.READY
    assert result.output.kind == IntentKind.DIRECT


def test_clarification_state():
    result = _run("")
    assert result.state == CognitiveState.CLARIFICATION_REQUIRED
    assert result.output.kind == IntentKind.CLARIFY


def test_error_state_on_invalid_input():
    core = CognitiveCore()
    with pytest.raises(Exception):
        core.process("x" * 2001, session_id="s", context_snapshot=[],
                     timestamp=1.0, source="test")
    assert core.state == CognitiveState.ERROR
    assert core.metrics["errors"] == 1


def test_illegal_transition_rejected():
    core = CognitiveCore()
    with pytest.raises(ValueError):
        core._go(CognitiveState.READY)  # depuis IDLE : interdit


def test_determinism_repeat():
    first = _run("Quelle heure est-il ?")
    second = _run("Quelle heure est-il ?")
    assert (first.output.kind, first.output.confidence, first.plan) == \
           (second.output.kind, second.output.confidence, second.plan)
    assert first.states == second.states


def test_callback_receives_event_only():
    seen = []
    core = CognitiveCore(on_result=seen.append)
    result = core.process("Ouvre YouTube", session_id="s",
                          context_snapshot=[], timestamp=1.0, source="test")
    assert seen == [result]
    assert result.output.kind == IntentKind.NEED_ACTION


def test_metrics():
    core = CognitiveCore()
    core.process("Bonjour", session_id="s", context_snapshot=[],
                 timestamp=1.0, source="test")
    core.process("xkzj qwx", session_id="s", context_snapshot=[],
                 timestamp=2.0, source="test")
    assert core.metrics["processed"] == 2
