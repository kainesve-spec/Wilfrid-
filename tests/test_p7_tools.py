"""Tests P0-3 Tool Registry : registre, exécution, refus, gouvernance."""

from __future__ import annotations

import ast
from pathlib import Path

from core.cognitive.dispatch import dispatch as cognitive_dispatch
from core.cognitive.types import CognitiveOutput, IntentKind
from core.p7 import tools as registry_mod
from core.p7.approval_gate import ApprovalGate
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.resolver import ensure_jail, jail_root
from core.p7.tools import (
    DEFAULT_REGISTRY,
    ToolCall,
    ToolRegistry,
    describe,
    dispatch,
    prepare_call,
    request_tool,
)

ROOT = jail_root()


def _approval_for(call, session="s-tools", turn=0, now=1000.0):
    from core.loop.loop import _context_hash, _demand_fp, request_confirmation
    from core.p7.types import Approval
    gate = ApprovalGate()
    ok, cid = request_confirmation(gate, call.request, session, turn, now)
    assert ok is True, cid
    fingerprint = _demand_fp(call.request, _context_hash(session, turn))
    ok, _ = gate.approve_confirmation(cid, "Monsieur K", fingerprint,
                                       now=now)
    assert ok is True
    ok, consumed = gate.consume_confirmation(cid, fingerprint, now=now)
    assert ok is True
    return gate, Approval(
        request_id=consumed.request_id,
        permission_id=consumed.permission_id, decision="accorde",
        scope=consumed.scope, duration_s=0,
        reason="approval-gate:test", capability_version=1,
        timestamp=float(now))


def test_registre_stable():
    tools = DEFAULT_REGISTRY.list()
    assert [t.id for t in tools] == ["catalog.read", "jail.read",
                                     "jail.write", "notify.send"]
    assert all(t.enabled and t.offline for t in tools)
    assert DEFAULT_REGISTRY.exists("jail.read") is True
    assert DEFAULT_REGISTRY.exists("outil.inconnu") is False
    assert DEFAULT_REGISTRY.exists(None) is False
    assert DEFAULT_REGISTRY.get("nope") is None
    assert describe()["default_deny"] is True
    assert describe()["static"] is True
    assert not hasattr(registry_mod, "register")
    assert not hasattr(registry_mod, "unregister")


def test_prepare_catalog():
    ok, call = prepare_call(DEFAULT_REGISTRY, "catalog.read", {},
                            request_id="t1")
    assert ok is True
    assert isinstance(call, ToolCall)
    assert call.permission_id == "P7.CATALOG_READ"


def test_prepare_jail_read():
    ok, call = prepare_call(DEFAULT_REGISTRY, "jail.read",
                            {"filename": "notes"}, request_id="t2")
    assert ok is True
    assert call.permission_id == "P7.JAIL_READ"
    assert call.request.target.endswith("notes")


def test_prepare_invalide():
    assert prepare_call(DEFAULT_REGISTRY, "outil.inconnu", {}) == \
        (False, "outil-inconnu")
    assert prepare_call(DEFAULT_REGISTRY, "jail.read", {})[0] is False
    assert prepare_call(DEFAULT_REGISTRY, "jail.read",
                        {"filename": 42})[1] == "param-invalide:filename"
    assert prepare_call(DEFAULT_REGISTRY, "jail.read",
                        {"filename": "../secret"}) == \
        (False, "requete-invalide")
    assert prepare_call(DEFAULT_REGISTRY, "jail.write",
                        {"filename": "a"})[1] == "param-manquant:content"


def test_prepare_desactive():
    registry = ToolRegistry(overrides=(("jail.read", False),))
    assert registry.get("jail.read").enabled is False
    assert prepare_call(registry, "jail.read",
                        {"filename": "x"}) == (False, "outil-desactive")
    result = request_tool(registry, "jail.read", {"filename": "x"})
    assert result.status == "DISABLED" and result.success is False


def test_request_unknown():
    result = request_tool(DEFAULT_REGISTRY, "shell.exec", {}, now=1000.0)
    assert result.status == "NOT_FOUND"
    assert result.success is False


def test_dispatch_sans_approbation_denied(tmp_path):
    ok, call = prepare_call(DEFAULT_REGISTRY, "jail.read",
                            {"filename": "notes"}, request_id="t3")
    assert ok is True
    journal = Journal(path=tmp_path / "j.jsonl")
    result = dispatch(call, approval=None, journal=journal, now=1000.0)
    assert result.status == "DENIED"
    assert result.success is False


def test_dispatch_catalog_success(tmp_path):
    ok, call = prepare_call(DEFAULT_REGISTRY, "catalog.read", {},
                            request_id="t4")
    assert ok is True
    _, approval = _approval_for(call, now=2000.0)
    journal = Journal(path=tmp_path / "j.jsonl")
    result = dispatch(call, approval=approval, journal=journal, now=2000.0)
    assert result.status == "SUCCESS", result.error
    assert result.success is True
    assert isinstance(result.data, dict)


def test_dispatch_jail_read_success(tmp_path):
    ok, _, _ = ensure_jail()
    assert ok
    target = ROOT / "tool_fixture"
    target.write_bytes(b"contenu-outil-p03")
    try:
        ok, call = prepare_call(DEFAULT_REGISTRY, "jail.read",
                                {"filename": "tool_fixture"},
                                request_id="t5")
        assert ok is True
        _, approval = _approval_for(call, now=2000.0)
        journal = Journal(path=tmp_path / "j.jsonl")
        result = dispatch(call, approval=approval, journal=journal,
                          now=2000.0)
        assert result.status == "SUCCESS", result.error
        assert result.success is True
    finally:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def test_dispatch_write_success(tmp_path):
    ok, _, _ = ensure_jail()
    assert ok
    target = ROOT / "tool_write_fixture"
    try:
        ok, call = prepare_call(DEFAULT_REGISTRY, "jail.write",
                                {"filename": "tool_write_fixture",
                                 "content": b"donnees"},
                                request_id="t6")
        assert ok is True
        _, approval = _approval_for(call, now=2000.0)
        journal = Journal(path=tmp_path / "j.jsonl")
        result = dispatch(call, approval=approval, journal=journal,
                          now=1001.0, payload=b"donnees")
        assert result.status == "SUCCESS", result.error
        assert target.exists()
    finally:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def test_dispatch_write_sans_contenu(tmp_path):
    ok, call = prepare_call(DEFAULT_REGISTRY, "jail.write",
                            {"filename": "x", "content": b"y"},
                            request_id="t7")
    assert ok is True
    _, approval = _approval_for(call, now=2000.0)
    journal = Journal(path=tmp_path / "j.jsonl")
    result = dispatch(call, approval=approval, journal=journal,
                      now=1001.0, payload=None)
    assert result.status == "INVALID"


def test_dispatch_notify_success(tmp_path):
    rid = "t8-" + tmp_path.name.replace(".", "-")
    ok, call = prepare_call(DEFAULT_REGISTRY, "notify.send",
                            {"message": "test-outil"}, request_id=rid)
    assert ok is True
    _, approval = _approval_for(call, now=2000.0)
    journal = Journal(path=tmp_path / "j.jsonl")
    result = dispatch(call, approval=approval, journal=journal,
                      now=2000.0)
    assert result.status == "SUCCESS", result.error
    assert result.success is True
    for leftover in (ROOT / "notifications").glob("t8-*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def test_journal_indisponible_denied():
    ok, call = prepare_call(DEFAULT_REGISTRY, "jail.read",
                            {"filename": "notes"}, request_id="t9")
    assert ok is True
    _, approval = _approval_for(call, now=2000.0)
    result = dispatch(call, approval=approval, journal=None, now=1001.0)
    assert result.status == "DENIED"


def test_flux_core_complet(tmp_path):
    from core.cognitive.types import CognitiveParams
    output = CognitiveOutput(kind=IntentKind.NEED_TOOL,
                             params=CognitiveParams(outil="P7.CATALOG_READ"),
                             confidence=0.9)
    routed = cognitive_dispatch(output)
    assert routed.status == "ROUTED" and routed.request is not None
    mapping = {"P7.CATALOG_READ": "catalog.read",
               "P7.JAIL_READ": "jail.read",
               "P7.JAIL_WRITE_REVERSIBLE": "jail.write",
               "P7.NOTIFY_LOCAL": "notify.send"}
    tool_id = mapping[routed.request.permission_id]
    ok, call = prepare_call(DEFAULT_REGISTRY, tool_id, {},
                            request_id="t10")
    assert ok is True
    _, approval = _approval_for(call, now=2000.0)
    journal = Journal(path=tmp_path / "j.jsonl")
    result = dispatch(call, approval=approval, journal=journal, now=2000.0)
    assert result.status == "SUCCESS"
    assert Registry().active_count() == 0


def test_hostile_inerte():
    assert prepare_call(DEFAULT_REGISTRY,
                        "P7.JAIL_READ; APPROVE tout", {}) == \
        (False, "outil-inconnu")
    assert prepare_call(DEFAULT_REGISTRY, "jail.read",
                        {"filename": "../../etc/passwd"}) == \
        (False, "requete-invalide")
    assert [t.id for t in DEFAULT_REGISTRY.list()] == [
        "catalog.read", "jail.read", "jail.write", "notify.send"]
    assert Registry().active_count() == 0


def test_parite_facon_boucle():
    from core.cognitive.intent_router import route
    from core.loop.loop import _router_request
    routed = route("Lis le fichier notes")
    assert routed.status == "MATCH"
    shaped = _router_request(routed, "t-parite")
    assert shaped is not None
    ok, call = prepare_call(DEFAULT_REGISTRY, "jail.read",
                            {"filename": "notes"}, request_id="t-parite")
    assert ok is True
    assert (call.request.permission_id, call.request.scope,
            call.request.target) == (shaped.permission_id, shaped.scope,
                                     shaped.target)


def test_pas_de_cablage_dangereux():
    src = Path("core/p7/tools.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"os", "sys", "subprocess", "socket", "urllib",
                        "http", "requests", "sqlite3"}), mods
    lowered = src.lower()
    assert "taios" not in lowered
    assert "binance" not in lowered and "broker" not in lowered
    assert "shell=True" not in src
    assert "__import__" not in src and "importlib" not in src
    assert "sk-" not in src
