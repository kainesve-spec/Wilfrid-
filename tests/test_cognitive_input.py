"""Tests P5 — validation d'entrée + copie profonde obligatoire."""

from __future__ import annotations

import pytest

from core.cognitive.input import CognitiveInputError, build_input


def _valid(**kw):
    base = dict(text="Bonjour", session_id="s1", context_snapshot=[],
                timestamp=1.0, source="test")
    base.update(kw)
    return build_input(**base)


def test_valid_input():
    inp = _valid()
    assert inp.text == "Bonjour" and inp.session_id == "s1"


def test_empty_text_accepted_for_classifier():
    # Le vide parvient au classifieur (qui émet CLARIFY), pas de rejet ici.
    inp = _valid(text="")
    assert inp.text == ""
    with pytest.raises(CognitiveInputError):
        _valid(text=123)  # type: ignore[arg-type]


def test_oversize_text_rejected():
    with pytest.raises(CognitiveInputError):
        _valid(text="x" * 2001)
    _valid(text="x" * 2000)


def test_invalid_session_id():
    with pytest.raises(CognitiveInputError):
        _valid(session_id="")


def test_invalid_timestamp_source_confidence():
    with pytest.raises(CognitiveInputError):
        _valid(timestamp=float("nan"))
    with pytest.raises(CognitiveInputError):
        _valid(source="")
    with pytest.raises(CognitiveInputError):
        _valid(stt_confidence=1.5)
    got = _valid(stt_confidence=0.7)
    assert got.stt_confidence == pytest.approx(0.7)


def test_snapshot_lengths():
    # Les cas 1-4 de copie profonde + source inchangée (cas 5) sont
    # couverts dans test_cognitive_core.py (section dédiée) ; ici :
    # le snapshot stocké n'est jamais l'objet fourni.
    src = [{"a": [1]}]
    inp = _valid(context_snapshot=src)
    assert inp.context_snapshot == src
    assert inp.context_snapshot is not src
