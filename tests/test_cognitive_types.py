"""Tests P5 — taxonomie et types (fermés, immuables)."""

from __future__ import annotations

import pytest

from core.cognitive.types import (
    TAXONOMY_VERSION,
    CognitiveOutput,
    CognitiveParams,
    IntentKind,
)


def test_exactly_eight_kinds():
    assert [k.value for k in IntentKind] == [
        "DIRECT", "CLARIFY", "PLAN", "NEED_SEARCH", "NEED_TOOL",
        "NEED_ACTION", "REFUSE", "UNCERTAIN",
    ]
    assert TAXONOMY_VERSION == "1.0"


def test_output_defaults_bounded():
    out = CognitiveOutput(IntentKind.DIRECT)
    assert 0.0 <= out.confidence <= 1.0
    assert out.missing == []
    assert isinstance(out.params, CognitiveParams)


def test_frozen_dataclasses():
    out = CognitiveOutput(IntentKind.DIRECT)
    with pytest.raises(Exception):
        out.confidence = 0.5  # type: ignore[misc]
