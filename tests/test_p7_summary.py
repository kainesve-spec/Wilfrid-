"""Tests K-δ — synthèse multi-requêtes (pure, vocabulaire fermé, 0 I/O)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.p7 import summary as S
from core.p7.audit import AuditRecord


def _ev(event: str, decision: str, version: int = 1) -> dict:
    return {"event": event, "decision": decision, "capability_version": version,
            "permission": "P7.JAIL_READ", "target": "t", "reason": "ok"}


def _rec(rid: str, *events: dict, corrupt: int = 0) -> AuditRecord:
    return AuditRecord(request_id=rid, p7_present=bool(events),
                       p6_present=False, session_present=False,
                       p7_events=tuple(events), p6_events=(),
                       session_events=(), corrupt_lines=corrupt,
                       reason="ok")


def test_empty_collection():
    result = S.summary(())
    assert result.total == 0 and result.state == "INCOMPLET"
    assert (result.coherent, result.incoherent, result.incomplete) == (0, 0, 0)


def test_single_coherent():
    result = S.summary((_rec("a", _ev("proof", "ALLOW")),))
    assert result.total == 1 and result.coherent == 1
    assert result.state == "COHERENT"


def test_multiple_coherent():
    result = S.summary(tuple(_rec(f"a{i}", _ev("proof", "ALLOW"))
                             for i in range(3)))
    assert (result.total, result.coherent) == (3, 3)
    assert result.state == "COHERENT"


def test_single_incomplete():
    result = S.summary((_rec("b"),))
    assert result.total == 1 and result.incomplete == 1
    assert result.state == "INCOMPLET"


def test_multiple_incomplete():
    result = S.summary((_rec("b1"), _rec("b2", corrupt=1)))
    assert (result.total, result.incomplete) == (2, 2)
    assert result.state == "INCOMPLET"


def test_single_incoherent():
    result = S.summary((_rec("c", _ev("proof", "ALLOW"),
                             _ev("proof", "DENY")),))
    assert result.total == 1 and result.incoherent == 1
    assert result.state == "INCOHERENT"


def test_coherent_plus_incomplete():
    result = S.summary((_rec("a", _ev("proof", "ALLOW")), _rec("b")))
    assert (result.coherent, result.incomplete) == (1, 1)
    assert result.state == "INCOMPLET"


def test_coherent_plus_incoherent():
    result = S.summary((_rec("a", _ev("proof", "ALLOW")),
                        _rec("c", _ev("proof", "ALLOW"),
                             _ev("proof", "DENY"))))
    assert result.state == "INCOHERENT"
    assert result.incoherent == 1 and result.coherent == 1


def test_all_three_mixed():
    result = S.summary((_rec("a", _ev("proof", "ALLOW")), _rec("b"),
                        _rec("c", _ev("proof", "ALLOW"),
                             _ev("proof", "DENY"))))
    assert (result.total, result.coherent, result.incoherent,
            result.incomplete) == (3, 1, 1, 1)
    assert result.state == "INCOHERENT"


def test_priority_incoherent():
    assert S.summary((_rec("c", _ev("x", "ALLOW"), _ev("x", "DENY")),)).state \
        == "INCOHERENT"
    assert S.summary((_rec("a", _ev("y", "ALLOW")),
                      _rec("b"))).state == "INCOMPLET"


def test_priority_incomplete_without_incoherent():
    result = S.summary((_rec("a", _ev("proof", "ALLOW")), _rec("b"),
                        _rec("d", corrupt=1)))
    assert result.incoherent == 0 and result.state == "INCOMPLET"


def test_determinism():
    records = (_rec("a", _ev("proof", "ALLOW")), _rec("b"))
    assert S.summary(records) == S.summary(records)
    assert S.summary(list(records)) == S.summary(records)


def test_input_immutability():
    records = (_rec("a", _ev("proof", "ALLOW")),)
    before = (records[0].p7_events, records[0].request_id)
    S.summary(records)
    assert (records[0].p7_events, records[0].request_id) == before


def test_invalid_inputs_controlled():
    for bad in (None, "texte", 123, {"a": 1}):
        result = S.summary(bad)
        assert result.total == 0 and result.state == "INCOMPLET"
    result = S.summary((None, "x", 42))
    assert result.total == 3 and result.incomplete == 3
    assert result.state == "INCOMPLET"


def test_no_io_no_authority_in_module():
    src = Path(__import__("core.p7.summary", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "typing", "core"}
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    forbidden_calls = {"open", "decide", "Approval", "Journal", "Registry",
                       "invoke", "audit", "verify_many", "mkdir", "unlink",
                       "write_bytes", "read_bytes", "socket", "Popen", "run",
                       "check_output", "system", "exec", "eval"}
    assert not (called & forbidden_calls), called & forbidden_calls
    assert "MissionSummary(" in src and "verify(" in src


def test_vocabulary_closed():
    assert {S.MissionSummary().state} <= {"COHERENT", "INCOHERENT", "INCOMPLET"}
    result = S.summary((_rec("a", _ev("proof", "ALLOW")),))
    assert result.state in ("COHERENT", "INCOHERENT", "INCOMPLET")
