"""Tests Approval Gate — verrou humain, sans exécution."""

from __future__ import annotations

import ast
from pathlib import Path

from core.p7.approval_gate import (
    ApprovalGate,
    demand_fingerprint,
)
from core.p7.registry import Registry


def _gate():
    return ApprovalGate()


def _create(gate, cid="c1", **over):
    params = dict(confirmation_id=cid, request_id="r1",
                  permission_id="P7.JAIL_READ",
                  scope="fichier:/JAIL/P7/a.txt:lecture-seule",
                  target="/JAIL/P7/a.txt",
                  limits={"files": 1}, context_hash="ctx",
                  expires_at=2000.0, now=1000.0)
    params.update(over)
    return gate.create_confirmation(**params)


def _fingerprint(cid="c1"):
    return demand_fingerprint(request_id="r1",
                              permission_id="P7.JAIL_READ",
                              scope="fichier:/JAIL/P7/a.txt:lecture-seule",
                              target="/JAIL/P7/a.txt",
                              limits={"files": 1}, context_hash="ctx")


def test_create_pending_valid():
    gate = _gate()
    ok, confirmation = _create(gate)
    assert ok is True and confirmation.state == "PENDING"
    assert confirmation.fingerprint == _fingerprint()
    assert gate.get("c1") == confirmation


def test_create_rejects_missing_data():
    gate = _gate()
    assert gate.create_confirmation("", "r", "P", "s", "t")[0] is False
    assert gate.create_confirmation("c", "", "P", "s", "t")[0] is False
    assert _create(gate, cid="c1")[0] is True
    assert _create(gate, cid="c1")[1] == "doublon"


def test_create_holds_no_secret():
    gate = _gate()
    ok, confirmation = _create(gate, scope="fichier:/JAIL/P7/a.txt:x")
    assert ok is True
    assert "SECRET" not in repr(confirmation)


def test_approve_exact():
    gate = _gate()
    _create(gate)
    ok, approved = gate.approve_confirmation("c1", "Monsieur K",
                                             _fingerprint(), now=1500.0)
    assert ok is True and approved.state == "APPROVED"
    assert approved.decided_by == "Monsieur K"


def test_approve_wrong_id_no_effect():
    gate = _gate()
    _create(gate)
    assert gate.approve_confirmation("zzz", "Monsieur K", _fingerprint(),
                                     now=1500.0)[1] == "inconnue"
    assert gate.get("c1").state == "PENDING"  # type: ignore[union-attr]


def test_approve_modified_demand_refused():
    gate = _gate()
    _create(gate)
    other = demand_fingerprint(request_id="r1", permission_id="P7.JAIL_READ",
                               scope="fichier:/JAIL/P7/b.txt:lecture-seule",
                               target="/JAIL/P7/b.txt",
                               limits={"files": 1}, context_hash="ctx")
    assert gate.approve_confirmation("c1", "Monsieur K", other,
                                     now=1500.0)[1] == "demande-modifiee"
    assert gate.approve_confirmation("c1", "", _fingerprint(),
                                     now=1500.0)[1] == "approbateur-requis"


def test_approve_consumed_refused():
    gate = _gate()
    _create(gate)
    gate.approve_confirmation("c1", "Monsieur K", _fingerprint(), now=1500.0)
    gate.consume_confirmation("c1", _fingerprint(), now=1600.0)
    assert gate.approve_confirmation("c1", "Monsieur K", _fingerprint(),
                                     now=1700.0)[1] == "etat-non-approuvable"


def test_deny_blocks_no_execution():
    gate = _gate()
    _create(gate)
    ok, denied = gate.deny_confirmation("c1", "Monsieur K",
                                        reason="non", now=1500.0)
    assert ok is True and denied.state == "DENIED"
    assert gate.approve_confirmation("c1", "Monsieur K", _fingerprint(),
                                     now=1600.0)[1] == "etat-non-approuvable"


def test_deny_repeat_no_side_effect():
    gate = _gate()
    _create(gate)
    first = gate.deny_confirmation("c1", "Monsieur K", now=1500.0)
    second = gate.deny_confirmation("c1", "Monsieur K", now=1600.0)
    assert first[0] is True and second[0] is True
    assert first[1] == second[1]
    assert len(gate.audit()) == 2


def test_expired_blocks():
    gate = _gate()
    _create(gate, expires_at=1200.0)
    ok, approved = gate.approve_confirmation("c1", "Monsieur K",
                                             _fingerprint(), now=1500.0)
    assert ok is False and approved == "etat-non-approuvable"
    current = gate.get("c1")
    assert current is not None and current.state == "EXPIRED"
    assert gate.consume_confirmation("c1", _fingerprint(),
                                     now=1600.0)[1] == "non-consommable"


def test_no_expiry_when_unset():
    gate = _gate()
    _create(gate, expires_at=None)
    ok, approved = gate.approve_confirmation("c1", "Monsieur K",
                                             _fingerprint(), now=99999.0)
    assert ok is True and approved.state == "APPROVED"


def test_consume_once_only():
    gate = _gate()
    _create(gate)
    gate.approve_confirmation("c1", "Monsieur K", _fingerprint(), now=1500.0)
    ok, consumed = gate.consume_confirmation("c1", _fingerprint(), now=1600.0)
    assert ok is True and consumed.state == "CONSUMED"
    assert gate.consume_confirmation("c1", _fingerprint(),
                                     now=1700.0)[1] == "non-consommable"
    assert gate.get("c1").state == "CONSUMED"  # type: ignore[union-attr]


def test_no_restore_consumed_to_approved():
    gate = _gate()
    _create(gate)
    gate.approve_confirmation("c1", "Monsieur K", _fingerprint(), now=1500.0)
    gate.consume_confirmation("c1", _fingerprint(), now=1600.0)
    for target_state in ("APPROVED", "PENDING", "DENIED"):
        assert gate.approve_confirmation("c1", "Monsieur K", _fingerprint(),
                                         now=1700.0)[0] is False
        assert gate.deny_confirmation("c1", "Monsieur K",
                                      now=1700.0)[0] is False
    assert gate.get("c1").state == "CONSUMED"  # type: ignore[union-attr]


def test_escalation_paths_refused_no_execution():
    gate = _gate()
    _create(gate)
    foreign = {"confirmation_id": "c1", "state": "APPROVED",
               "fingerprint": _fingerprint(), "decided_by": "agent-x"}
    assert gate.consume_confirmation("c1", foreign["fingerprint"],
                                     now=1500.0)[1] == "non-consommable"
    assert gate.approve_confirmation("c1", "", _fingerprint(),
                                     now=1500.0)[1] == "approbateur-requis"
    other_cap = demand_fingerprint(
        request_id="r1", permission_id="P7.NOTIFY_LOCAL",
        scope="x", target="y", limits={}, context_hash="ctx")
    assert gate.approve_confirmation("c1", "Monsieur K", other_cap,
                                     now=1500.0)[1] == "demande-modifiee"
    reg = Registry()
    assert reg.active_count() == 0


def test_audit_coherent_no_secret():
    gate = _gate()
    _create(gate)
    gate.approve_confirmation("c1", "Monsieur K", _fingerprint(), now=1500.0)
    gate.consume_confirmation("c1", _fingerprint(), now=1600.0)
    events = gate.audit()
    assert [event.event for event in events] == ["CREATE", "APPROVE",
                                                 "CONSUME"]
    assert [event.seq for event in events] == [1, 2, 3]
    assert "SECRET" not in repr(events)


def test_no_forbidden_wiring():
    src = Path("core/p7/approval_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "typing", "hashlib"}
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(
                node.func, ast.Attribute):
            called.add(node.func.attr)
    assert not (called & {"open", "eval", "exec", "compile", "__import__",
                          "input", "Popen", "run", "system", "socket",
                          "connect", "decide", "enable", "grant"}), called
    code_only = src
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                code_only = code_only.replace(doc, "", 1)
    for token in ("Governor", "PermissionRegistry(", "Approval(",
                  "subprocess", "socket.", "os.", "sys."):
        assert token not in code_only, token
