"""Tests K-α — routeur d'effets (façade, sans autorité, zéro effet réel).

Les quatre handlers sont espionnés (monkeypatch des attributs de module, que le
routeur résout dynamiquement) : aucun test n'exécute d'opération réelle
(fichier, réseau, notification). But : prouver la sélection exacte, le DENY
contrôlé et l'absence de logique d'autorité dans le routeur.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import invoke as I
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.types import Approval, Proof, Request


def _request(pid: str, rid: str = "r-1") -> Request:
    scopes = {
        "P7.CATALOG_READ": "catalogue:P7.CATALOG_READ:lecture-seule",
        "P7.JAIL_READ": "fichier:/JAIL/P7/a.txt:lecture-seule",
        "P7.JAIL_WRITE_REVERSIBLE": "fichier:/JAIL/P7/a.txt:ecriture-bornee",
        "P7.NOTIFY_LOCAL": "notification:canal-local:textuel-borne",
    }
    targets = {
        "P7.CATALOG_READ": "P7.CATALOG_READ",
        "P7.JAIL_READ": "/JAIL/P7/a.txt",
        "P7.JAIL_WRITE_REVERSIBLE": "/JAIL/P7/a.txt",
        "P7.NOTIFY_LOCAL": "canal-local",
    }
    return Request(request_id=rid, skill_id="s", skill_version="1",
                   permission_id=pid, scope=scopes[pid], target=targets[pid],
                   limits={}, duration_s=60, reason="t")


def _approval(req: Request) -> Approval:
    return Approval(request_id=req.request_id, permission_id=req.permission_id,
                    decision="accorde", scope=req.scope, duration_s=60,
                    reason="ok", capability_version=1, timestamp=1000.0)


def _ok_decision(req: Request) -> G.Decision:
    return G.Decision(True, "ok", Proof(req.request_id, req.permission_id,
                                        "ALLOW", "ok", 1, ("stub",)))


def _stub_for(monkeypatch, module_path: str, func: str, calls: list):
    import importlib
    module = importlib.import_module(module_path)

    def spy(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        req = kwargs.get("request", args[0] if args else None)
        appr = kwargs.get("approval", args[1] if len(args) > 1 else None)
        calls[-1]["request"] = req
        calls[-1]["approval"] = appr
        return _ok_decision(req), {"stubbed": func}
    monkeypatch.setattr(module, func, spy)
    return spy


def test_route_ids_exact():
    assert I.route_ids() == ("P7.CATALOG_READ", "P7.JAIL_READ",
                             "P7.JAIL_WRITE_REVERSIBLE", "P7.NOTIFY_LOCAL")


def test_table_immutable():
    import pytest
    with pytest.raises(TypeError):
        I._ROUTES["P7.X"] = lambda **k: None


def test_exact_routing_four_permissions(monkeypatch, tmp_path):
    journal = Journal(path=None)
    cases = [
        ("core.p7.catalog", "evaluate", "P7.CATALOG_READ", None, {}),
        ("core.p7.reader", "read_one", "P7.JAIL_READ", None, {}),
        ("core.p7.writer", "write_one", "P7.JAIL_WRITE_REVERSIBLE",
         b"data", {}),
        ("core.p7.notify", "notify", "P7.NOTIFY_LOCAL", "hello", {}),
    ]
    for module_path, func, pid, payload, extra in cases:
        calls: list = []
        _stub_for(monkeypatch, module_path, func, calls)
        req = _request(pid, rid=f"r-{pid}")
        appr = _approval(req)
        before = sorted(p.name for p in tmp_path.iterdir())
        if pid == "P7.CATALOG_READ":
            res = I.invoke(permission_id=pid, request=req, approval=appr,
                           now=1000.0, journal=journal, payload=payload)
        else:
            res = I.invoke(permission_id=pid, request=req, approval=appr,
                           now=1000.0, journal=journal, payload=payload,
                           **extra)
        assert res.status == "ROUTED", pid
        assert res.decision is not None and res.decision.allowed is True
        assert len(calls) == 1
        assert calls[0]["request"] is req
        assert calls[0]["approval"] is appr
        assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_unknown_permission_deny_no_handler(monkeypatch, tmp_path):
    called: list = []
    for module_path, func in [("core.p7.catalog", "evaluate"),
                              ("core.p7.reader", "read_one"),
                              ("core.p7.writer", "write_one"),
                              ("core.p7.notify", "notify")]:
        _stub_for(monkeypatch, module_path, func, called)
    req = _request("P7.JAIL_READ", rid="r-unknown")
    before = sorted(p.name for p in tmp_path.iterdir())
    res = I.invoke(permission_id="P7.NOPE", request=req, approval=None,
                   now=1000.0, journal=Journal(path=None))
    assert res.status == "DENY"
    assert res.decision is None
    assert res.reason == E.PERMISSION_UNKNOWN
    assert called == []
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_invalid_payload_controlled_deny(monkeypatch, tmp_path):
    calls: list = []
    _stub_for(monkeypatch, "core.p7.writer", "write_one", calls)
    _stub_for(monkeypatch, "core.p7.notify", "notify", calls)
    _stub_for(monkeypatch, "core.p7.reader", "read_one", calls)
    journal = Journal(path=None)
    req_w = _request("P7.JAIL_WRITE_REVERSIBLE", rid="r-p1")
    res = I.invoke(permission_id="P7.JAIL_WRITE_REVERSIBLE", request=req_w,
                   approval=None, now=1000.0, journal=journal,
                   payload="pas-des-octets")
    assert res.status == "DENY" and res.reason == E.REQUEST_INVALID
    req_n = _request("P7.NOTIFY_LOCAL", rid="r-p2")
    res = I.invoke(permission_id="P7.NOTIFY_LOCAL", request=req_n,
                   approval=None, now=1000.0, journal=journal, payload=b"x")
    assert res.status == "DENY" and res.reason == E.REQUEST_INVALID
    req_r = _request("P7.JAIL_READ", rid="r-p3")
    res = I.invoke(permission_id="P7.JAIL_READ", request=req_r,
                   approval=None, now=1000.0, journal=journal,
                   payload="surprise")
    assert res.status == "DENY" and res.reason == E.REQUEST_INVALID
    assert calls == []
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_missing_data_controlled_deny(monkeypatch, tmp_path):
    calls: list = []
    _stub_for(monkeypatch, "core.p7.writer", "write_one", calls)
    journal = Journal(path=None)
    req = _request("P7.JAIL_WRITE_REVERSIBLE", rid="r-m1")
    assert I.invoke(permission_id="P7.JAIL_WRITE_REVERSIBLE", request=None,
                     approval=None, now=1000.0, journal=journal,
                     payload=b"d").status == "DENY"
    assert I.invoke(permission_id="P7.JAIL_WRITE_REVERSIBLE", request=req,
                     approval=None, now=None, journal=journal,
                     payload=b"d").status == "DENY"
    assert I.invoke(permission_id="P7.JAIL_WRITE_REVERSIBLE", request=req,
                     approval=None, now=1000.0, journal=None,
                     payload=b"d").reason == E.JOURNAL_UNAVAILABLE
    other = _request("P7.JAIL_READ", rid="r-m2")
    assert I.invoke(permission_id="P7.JAIL_WRITE_REVERSIBLE", request=other,
                     approval=None, now=1000.0, journal=journal,
                     payload=b"d").status == "DENY"
    assert calls == []
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_determinism(monkeypatch):
    calls: list = []
    _stub_for(monkeypatch, "core.p7.reader", "read_one", calls)
    journal = Journal(path=None)
    kwargs = dict(permission_id="P7.JAIL_READ",
                  request=_request("P7.JAIL_READ", rid="r-det"),
                  approval=None, now=1000.0, journal=journal)
    first = I.invoke(**kwargs)
    second = I.invoke(**kwargs)
    assert first == second
    assert len(calls) == 2


def test_no_approval_fabrication_or_registry_touch(monkeypatch):
    calls: list = []
    _stub_for(monkeypatch, "core.p7.reader", "read_one", calls)
    reg = Registry()
    before = reg.status()
    journal = Journal(path=None)
    req = _request("P7.JAIL_READ", rid="r-a1")
    appr = _approval(req)
    I.invoke(permission_id="P7.JAIL_READ", request=req, approval=appr,
             now=1000.0, journal=journal)
    assert calls[0]["approval"] is appr
    assert reg.status() == before and reg.active_count() == 0


def test_no_authority_logic_in_router():
    src = Path(__import__("core.p7.invoke", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "decide" not in called
    assert "enable" not in called and "grant" not in called
    assert "Approval(" not in src


def test_no_network_subprocess_imports():
    src = Path(__import__("core.p7.invoke", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"socket", "subprocess", "webbrowser", "os", "sys",
                        "sqlite3", "requests", "urllib", "ftplib", "httpx"})
    assert "core" in mods
