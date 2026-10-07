"""Tests C1 — fondations P7.1 (deny-by-default, zéro effet, P5/P6 intacts)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import lifecycle as LC
from core.p7 import types as T
from core.p7.journal import Journal, JournalUnavailable
from core.p7.registry import Registry


CATALOG_SCOPE = "catalogue:déclaré:lecture-seule"
JAIL = "~/Wilfrid/JAIL/P7"
NOTIF = "~/Wilfrid/JAIL/P7/notifications/"


def _req(**over) -> T.Request:
    base = dict(request_id="r-1", skill_id="s-1", skill_version="1",
                permission_id="P7.JAIL_READ",
                scope=f"fichier:{JAIL}/a.txt:lecture-seule",
                target=f"{JAIL}/a.txt",
                limits={"files": 1, "total_bytes": 100, "file_bytes": 100,
                        "depth": 1, "timeout_s": 1},
                duration_s=60, reason="test")
    base.update(over)
    return T.Request(**base)


def _appr(req: T.Request, **over) -> T.Approval:
    base = dict(request_id=req.request_id, permission_id=req.permission_id,
                decision="accorde", scope=req.scope, duration_s=req.duration_s,
                reason="ok", capability_version=2, timestamp=1000.0)
    base.update(over)
    return T.Approval(**base)


def test_registry_empty_by_default():
    reg = Registry()
    assert reg.is_empty() is True
    assert reg.active_count() == 0
    assert reg.status() == []


def test_absent_permission_denied():
    reg = Registry()
    allowed, reason = reg.check("P7.JAIL_READ", "x")
    assert allowed is False and reason == E.PERMISSION_UNKNOWN
    d = G.decide(_req(permission_id="P7.UNKNOWN_ID"), None, 1000.0, True)
    assert d.allowed is False and d.reason == E.PERMISSION_UNKNOWN


def test_absent_approval_denied():
    d = G.decide(_req(), None, 1000.0, True)
    assert d.allowed is False and d.reason == E.APPROVAL_ABSENT


def test_expired_approval_denied():
    req = _req()
    appr = _appr(req, timestamp=1000.0, duration_s=60)
    d = G.decide(req, appr, 2000.0, True)
    assert d.allowed is False and d.reason == E.APPROVAL_EXPIRED


def test_revoked_denied_registry_and_governor():
    reg = Registry()
    reg.declare("P7.JAIL_READ", scope="s", limits={})
    reg.revoke("P7.JAIL_READ", reason="k")
    allowed, reason = reg.check("P7.JAIL_READ", "x")
    assert allowed is False and reason == E.CAPABILITY_REVOKED
    req = _req()
    d = G.decide(req, _appr(req, revoked=True), 1000.0, True)
    assert d.allowed is False and d.reason == E.CAPABILITY_REVOKED
    d2 = G.decide(req, _appr(req, suspended=True), 1000.0, True)
    assert d2.allowed is False and d2.reason == E.CAPABILITY_SUSPENDED


def test_invalid_scope_denied():
    req = _req(scope="fichier:*:lecture-seule", target="x")
    assert G.decide(req, _appr(req), 1000.0, True).reason in (
        E.SCOPE_INVALID, E.SCOPE_NOT_COVERING)
    req2 = _req(target=f"{JAIL}/voisin.txt")
    d2 = G.decide(req2, _appr(req2), 1000.0, True)
    assert d2.allowed is False and d2.reason == E.SCOPE_NOT_COVERING
    req3 = _req(scope="fichier:~/Wilfrid/JAIL/P7/a.txt:lecture-seule",
                target="~/Wilfrid/JAIL/P7/../evil.txt")
    d3 = G.decide(req3, _appr(req3), 1000.0, True)
    assert d3.allowed is False


def test_invalid_limits_denied():
    req = _req(limits={"files": 99, "total_bytes": 100, "file_bytes": 100,
                       "depth": 1, "timeout_s": 1})
    assert G.decide(req, _appr(req), 1000.0, True).reason == E.LIMITS_INVALID
    req2 = _req(duration_s=999999)
    assert G.decide(req2, _appr(req2), 1000.0, True).reason == E.LIMITS_INVALID


def test_journal_unavailable_denied_total(tmp_path):
    j = Journal(path=None)
    assert j.available() is False
    with pytest.raises(JournalUnavailable):
        j.record(event="demand")
    req = _req()
    d = G.decide(req, _appr(req), 1000.0, False)
    assert d.allowed is False and d.reason == E.JOURNAL_UNAVAILABLE
    ok, why = G.journal_gate(False)
    assert ok is False and why == E.JOURNAL_UNAVAILABLE


def test_journal_writes_only_technical_fields(tmp_path):
    p = tmp_path / "p7.jsonl"
    j = Journal(path=p)
    evt = j.record(event="demand", actor="core", request_id="r-1",
                   permission_id="P7.JAIL_READ", target="t" * 500,
                   decision="DENY", reason="r" * 500, capability_version=2,
                   risk="R1")
    assert p.is_file()
    line = json.loads(p.read_bytes().decode("utf-8").splitlines()[0])
    assert len(line["target"]) <= 256 and len(line["reason"]) <= 256
    assert "secret" not in line and ".env" not in json.dumps(line)


def test_unknown_error_denied():
    d = G.decide(None, None, 1000.0, True)  # type: ignore[arg-type]
    assert d.allowed is False
    d2 = G.decide("garbage", "garbage", 1000.0, True)  # type: ignore[arg-type]
    assert d2.allowed is False and d2.reason in E.CLOSED_CODES


def test_lifecycle_invalid_denied():
    assert LC.is_valid_transition("PROPOSÉ", "ACTIF")[0] is False
    assert LC.is_valid_transition("NOPE", "ACTIF")[0] is False
    assert LC.is_valid_transition("REFUSÉ", "ACTIF")[0] is False
    assert LC.is_valid_transition("RETIRÉ", "ACTIVÉ")[0] is False
    assert LC.is_valid_transition("PROPOSÉ", "DÉCLARÉ")[0] is True


def test_no_b2_capability_produces_effect(tmp_path):
    import core.p7 as p7pkg
    root = Path(p7pkg.__file__).parent
    names = {p.name for p in root.iterdir() if p.suffix == ".py"}
    assert names <= {"__init__.py", "types.py", "errors.py", "registry.py",
                     "journal.py", "lifecycle.py", "governor.py",
                     "catalog.py", "resolver.py", "reader.py", "writer.py",
                     "notify.py", "invoke.py", "audit.py",
                     "coherence.py", "summary.py", "status.py",
                     "approval_gate.py"}, names - {"__init__.py", "types.py", "errors.py",
                     "registry.py", "journal.py", "lifecycle.py", "governor.py",
                     "catalog.py", "resolver.py", "reader.py", "writer.py",
                     "notify.py", "invoke.py", "audit.py",
                     "coherence.py", "summary.py", "status.py",
                     "approval_gate.py"}
    before = sorted(p.name for p in tmp_path.iterdir())
    req = _req()
    G.decide(req, None, 1000.0, False)
    G.decide(req, _appr(req, revoked=True), 1000.0, False)
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after == []


def test_zero_effect_for_deny_series(tmp_path):
    marker = tmp_path / "probe.txt"
    marker.write_text("intact", encoding="utf-8")
    digest = marker.read_bytes()
    cases = [
        G.decide(_req(), None, 1000.0, False),
        G.decide(_req(target=f"{JAIL}/voisin.txt"),
                 _appr(_req(target=f"{JAIL}/voisin.txt")), 1000.0, False),
        G.decide(_req(), _appr(_req(), revoked=True), 1000.0, False),
    ]
    assert all(c.allowed is False for c in cases)
    assert marker.read_bytes() == digest
    assert sorted(p.name for p in tmp_path.iterdir()) == ["probe.txt"]


def test_no_forbidden_imports_in_p7():
    import core.p7 as p7pkg
    banned = {"subprocess", "socket", "requests", "httpx", "urllib",
              "ftplib", "webbrowser", "os", "sys", "sqlite3"}
    banned_calls = {"eval", "exec", "compile", "__import__", "system", "popen"}
    root = Path(p7pkg.__file__).parent
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (mods & banned), f"{path.name}: {mods & banned}"
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not (calls & banned_calls), f"{path.name}: {calls & banned_calls}"


def test_p6_intact():
    from core.knowledge.permissions import PERMISSION_IDS
    assert len(PERMISSION_IDS) == 8
    meta = json.loads(Path("models/wake.json").read_text(encoding="utf-8"))
    assert abs(float(meta["threshold"]) - 0.665) < 1e-9


def test_p5_intact():
    from core.cognitive import planner as P
    from core.cognitive.types import CognitiveOutput, IntentKind
    out = CognitiveOutput(IntentKind.NEED_ACTION,
                          __import__("core.cognitive.types", fromlist=["x"]).CognitiveParams(),
                          0.5, [])
    plan = P.build_plan(out)
    assert isinstance(plan, list) and plan[0]["name"] == "action_requise"
