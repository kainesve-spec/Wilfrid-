"""Tests CATALOG_READ — R0 déclaratif, 0 effet, fail-closed."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from core.p7 import catalog as C
from core.p7 import errors as E
from core.p7.catalog import CatalogEntry
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.types import Approval, Request


def _req(entry_id: str = "P7.CATALOG_READ", **over) -> Request:
    base = dict(request_id="c-1", skill_id="s-1", skill_version="1",
                permission_id="P7.CATALOG_READ",
                scope=C.scope_for(entry_id), target=entry_id,
                limits={"entries": 1, "bytes": 100},
                duration_s=600, reason="test")
    base.update(over)
    return Request(**base)


def _appr(req: Request, **over) -> Approval:
    base = dict(request_id=req.request_id, permission_id=req.permission_id,
                decision="accorde", scope=req.scope, duration_s=req.duration_s,
                reason="ok", capability_version=1, timestamp=1000.0)
    base.update(over)
    return Approval(**base)


def test_exact_entry_allow_and_journaled(tmp_path):
    cat = C.build_catalog()
    req = _req()
    dec, payload = C.evaluate(req, _appr(req), 1000.0, True, cat)
    assert dec.allowed is True and payload is not None
    assert payload["id"] == "P7.CATALOG_READ"
    assert C.response_bytes(C.CatalogEntry(**payload)) <= 8192
    jp = tmp_path / "p7.jsonl"
    j = Journal(path=jp)
    evt = j.record(event="proof", actor="core", request_id=req.request_id,
                   permission_id=req.permission_id, target=req.target,
                   decision="ALLOW", reason="ok",
                   capability_version=dec.proof.capability_version, risk="R0")
    assert evt["decision"] == "ALLOW" and jp.is_file()


def test_absent_entry_deny():
    cat = C.build_catalog()
    req = _req(entry_id="P7.INEXISTANT")
    dec, payload = C.evaluate(req, _appr(req), 1000.0, True, cat)
    assert dec.allowed is False and payload is None


def test_neighbor_entry_deny():
    cat = C.build_catalog()
    req = _req(entry_id="P7.CATALOG_REAd")
    dec, payload = C.evaluate(req, _appr(req), 1000.0, True, cat)
    assert dec.allowed is False and payload is None


def test_ambiguous_target_deny():
    cat = C.build_catalog()
    for bad in ("", "*", "P7.*", "P7.CATALOG_READ/../X", "  "):
        req = _req(entry_id=bad)
        dec, _ = C.evaluate(req, _appr(req), 1000.0, True, cat)
        assert dec.allowed is False, bad


def test_over_50_entries_deny():
    big = tuple(CatalogEntry(f"P7.E{i:03d}", "R0", "d") for i in range(51))
    ok, why, _ = C.list_entries(big, 51)
    assert ok is False and why == E.LIMITS_INVALID
    ok2, _, _ = C.list_entries(C.build_catalog(), 51)
    assert ok2 is False


def test_response_over_8kb_deny():
    huge = CatalogEntry("P7.HUGE", "R0", "x" * 9000)
    assert C.response_bytes(huge) > 8192
    ok, _, _ = C.list_entries((huge,), 1)
    assert ok is False
    found, why, entry = C.lookup((huge,), "P7.HUGE")
    assert found is False and entry is None


def test_expiry_revocation_suspension_deny():
    cat = C.build_catalog()
    req = _req()
    assert C.evaluate(req, _appr(req, timestamp=1000.0, duration_s=60),
                      5000.0, True, cat)[0].reason == E.APPROVAL_EXPIRED
    assert C.evaluate(req, _appr(req, revoked=True),
                      1000.0, True, cat)[0].reason == E.CAPABILITY_REVOKED
    assert C.evaluate(req, _appr(req, suspended=True),
                      1000.0, True, cat)[0].reason == E.CAPABILITY_SUSPENDED
    assert C.evaluate(req, None, 1000.0, True, cat)[0].reason == E.APPROVAL_ABSENT


def test_wrong_scope_deny():
    cat = C.build_catalog()
    req = _req()
    bad = Request(**{**req.__dict__, "scope": "catalogue:déclaré:lecture-seule"})
    dec, payload = C.evaluate(bad, _appr(bad), 1000.0, True, cat)
    assert dec.allowed is False and payload is None


def test_journal_unavailable_deny():
    cat = C.build_catalog()
    req = _req()
    dec, payload = C.evaluate(req, _appr(req), 1000.0, False, cat)
    assert dec.allowed is False and dec.reason == E.JOURNAL_UNAVAILABLE
    assert payload is None


def test_no_state_mutation_no_fs_write(tmp_path):
    cat = C.build_catalog()
    before = tuple(e.id for e in cat)
    reg = Registry()
    req = _req()
    C.evaluate(req, None, 1000.0, False, cat)
    C.evaluate(_req(entry_id="P7.NOPE"), _appr(_req(entry_id="P7.NOPE")),
               1000.0, False, cat)
    assert tuple(e.id for e in cat) == before
    assert reg.is_empty() and reg.active_count() == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_no_other_capability_activated():
    import core.p7 as p7pkg
    names = {p.name for p in Path(p7pkg.__file__).parent.iterdir()
             if p.suffix == ".py"}
    assert "scheduler.py" not in names and "executor.py" not in names
    assert "network.py" not in names
    reg = Registry()
    assert reg.active_count() == 0


def test_catalog_never_grants_or_modifies():
    import inspect
    src = Path(__import__("core.p7.catalog", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    for token in ("enable", "grant", "revoke", "open(", "write(",
                  "socket", "subprocess", "webbrowser", "os.", "sys.",
                  "sqlite3", "requests", "eval(", "exec("):
        assert token not in src, token


def test_catalog_imports_clean():
    import core.p7.catalog as mod
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"os", "sys", "socket", "subprocess", "webbrowser",
                        "sqlite3", "requests", "urllib", "ftplib", "httpx"})


def test_p6_p5_intact():
    from core.knowledge.permissions import PERMISSION_IDS
    assert len(PERMISSION_IDS) == 8
    meta = json.loads(Path("models/wake.json").read_text(encoding="utf-8"))
    assert abs(float(meta["threshold"]) - 0.665) < 1e-9
    from core.cognitive import planner as P
    from core.cognitive.types import CognitiveOutput, IntentKind
    out = CognitiveOutput(IntentKind.NEED_ACTION,
                          __import__("core.cognitive.types", fromlist=["x"]).CognitiveParams(),
                          0.5, [])
    assert P.build_plan(out)[0]["name"] == "action_requise"
