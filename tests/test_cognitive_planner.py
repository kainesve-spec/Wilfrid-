"""Tests P5 — planner abstrait : borné, sans I/O, sans exécution."""

from __future__ import annotations

from core.cognitive.classifier import classify
from core.cognitive.decider import decide
from core.cognitive.input import build_input
from core.cognitive.planner import build_plan, plan_is_effect_free
from core.cognitive.types import IntentKind


def _decided(text: str):
    inp = build_input(text=text, session_id="s", context_snapshot=[],
                      timestamp=1.0, source="test")
    return decide(classify(inp.text), inp), text


def test_valid_bounded_plans():
    for text in ["Ouvre YouTube",
                 "Quelle est la capitale de l'Espagne ?",
                 "Quelle heure est-il ?",
                 "Prépare ma journée de demain étape par étape",
                 "Bonjour Wilfrid"]:
        decision, raw = _decided(text)
        plan = build_plan(decision, raw)
        assert plan_is_effect_free(plan)
        assert len(plan) <= 8


def test_need_action_plan_declares_without_executing():
    decision, _raw = _decided("Supprime le fichier notes.txt")
    assert decision.kind == IntentKind.NEED_ACTION
    plan = build_plan(decision, "Supprime le fichier notes.txt")
    assert plan and plan[0]["requires"] == "ACTION"
    assert plan_is_effect_free(plan)
    # Aucun fichier touché par la planification elle-même.
    import pathlib

    assert not pathlib.Path("notes.txt").exists()


def test_plan_steps_from_markers():
    decision, raw = _decided("Prépare ma journée de demain étape par étape")
    assert decision.kind == IntentKind.PLAN
    plan = build_plan(decision, raw)
    assert 1 <= len(plan) <= 8
    assert all(set(s) == {"index", "name", "requires", "expected"}
               for s in plan)


def test_no_plan_for_closed_kinds():
    for text in ["Bonjour", "", "xkzj qwx"]:
        decision, raw = _decided(text)
        assert build_plan(decision, raw) == []


def test_effect_free_guard_rejects_garbage():
    assert plan_is_effect_free([{"index": "0"}]) is False
    assert plan_is_effect_free([{"index": "0", "name": "x", "requires": "",
                                 "expected": "", "run": "rm -rf /"}]) is False
    assert plan_is_effect_free([{"index": "0", "name": "x" * 81,
                                 "requires": "", "expected": ""}]) is False
