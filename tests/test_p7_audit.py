"""Tests K-β — vue d'audit lecture seule (corrélation par request_id).

Journaux temporaires contrôlés uniquement (`tmp_path`) : jamais les journaux
opérationnels réels. Chaque test vérifie l'absence d'écriture par snapshot.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from core.p7 import audit as A
from core.p7.journal import Journal
from core.p7.registry import Registry


def _write(path: Path, *entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as fh:
        for entry in entries:
            fh.write((json.dumps(entry, ensure_ascii=False) + "\n").encode())


def _snap(directory: Path) -> dict:
    state = {}
    for p in sorted(directory.rglob("*")):
        if p.is_symlink():
            state[str(p)] = "SYMLINK"
        elif p.is_file():
            state[str(p)] = (p.stat().st_size, p.stat().st_mtime_ns,
                             p.read_bytes())
    return state


def _p7ev(rid: str, **over) -> dict:
    base = {"timestamp": 1000.0, "event": "proof", "actor": "core",
            "request_id": rid, "permission": "P7.JAIL_READ",
            "target": "t", "decision": "ALLOW", "reason": "ok",
            "capability_version": 1, "risk": "R1"}
    base.update(over)
    return base


def test_nominal_correlation(tmp_path):
    p7 = tmp_path / "p7.jsonl"
    p6 = tmp_path / "p6.jsonl"
    sess = tmp_path / "sess.jsonl"
    Journal(path=p7).record(event="proof", actor="core", request_id="r-1",
                            permission_id="P7.JAIL_READ", target="t",
                            decision="ALLOW", reason="ok",
                            capability_version=1, risk="R1")
    _write(p6, {"timestamp": 1.0, "action": "download",
                "permission": "SOURCE_ACCESS", "target": "u",
                "decision": "ALLOW", "reason": "ok", "job_id": "j1",
                "config_version": 1, "request_id": "r-1"})
    _write(sess, {"event": "ENDED", "session_id": "s1", "request_id": "r-1",
                  "cause": "close", "state": "IDLE"})
    rec = A.audit("r-1", p7_path=p7, p6_path=p6, session_path=sess)
    assert rec.request_id == "r-1"
    assert rec.p7_present and rec.p6_present and rec.session_present
    assert rec.p7_events[0]["decision"] == "ALLOW"
    assert rec.p6_events[0]["job_id"] == "j1"
    assert rec.session_events[0]["session_id"] == "s1"
    assert rec.reason == "ok"


def test_partial_traces(tmp_path):
    p7 = tmp_path / "p7.jsonl"
    _write(p7, _p7ev("r-2"))
    rec = A.audit("r-2", p7_path=p7)
    assert rec.p7_present and not rec.p6_present
    assert not rec.session_present
    assert "p6:journal-absent" in rec.reason


def test_unknown_request_id(tmp_path):
    p7 = tmp_path / "p7.jsonl"
    _write(p7, _p7ev("r-3"))
    rec = A.audit("r-zzz", p7_path=p7)
    assert not rec.p7_present and rec.p7_events == ()
    assert "p7:sans-trace" in rec.reason


def test_absent_journals():
    rec = A.audit("r-4")
    assert (rec.p7_present, rec.p6_present, rec.session_present) == (
        False, False, False)
    assert rec.corrupt_lines == 0
    rec2 = A.audit("r-4", p7_path="/nonexistent/x.jsonl")
    assert not rec2.p7_present


def test_empty_files(tmp_path):
    p7 = tmp_path / "empty.jsonl"
    p7.write_bytes(b"")
    rec = A.audit("r-5", p7_path=p7)
    assert not rec.p7_present and rec.corrupt_lines == 0


def test_corrupt_lines_counted(tmp_path):
    p7 = tmp_path / "bad.jsonl"
    p7.write_bytes(b"{not json\n" + b"[1,2]\n"
                   + (json.dumps(_p7ev("r-6")) + "\n").encode())
    rec = A.audit("r-6", p7_path=p7)
    assert rec.p7_present and rec.corrupt_lines == 2


def test_entry_without_request_id_not_attached(tmp_path):
    p7 = tmp_path / "noid.jsonl"
    _write(p7, {"event": "proof", "decision": "ALLOW"},
           _p7ev("r-7"))
    rec = A.audit("r-7", p7_path=p7)
    assert len(rec.p7_events) == 1
    rec2 = A.audit("other", p7_path=p7)
    assert not rec2.p7_present


def test_determinism(tmp_path):
    p7 = tmp_path / "det.jsonl"
    _write(p7, _p7ev("r-8"), _p7ev("r-8", event="pre-read"))
    kwargs = dict(p7_path=p7)
    assert A.audit("r-8", **kwargs) == A.audit("r-8", **kwargs)


def test_read_only_snapshot(tmp_path):
    p7 = tmp_path / "ro.jsonl"
    _write(p7, _p7ev("r-9"))
    before = _snap(tmp_path)
    A.audit("r-9", p7_path=p7, p6_path=tmp_path / "nope.jsonl")
    A.audit(None, p7_path=p7)
    assert _snap(tmp_path) == before


def test_no_writes_network_subprocess_no_governor():
    src = Path(__import__("core.p7.audit", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "typing", "pathlib", "json"}
    assert "core" not in mods
    assert "decide(" not in src and "Approval(" not in src
    assert "open(" not in src or ".read_bytes(" in src


def test_no_approval_permission_registry_touch():
    reg = Registry()
    assert reg.status() == [] and reg.active_count() == 0
    src = Path(__import__("core.p7.audit", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any("registry" in a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert "registry" not in (node.module or "")
            assert not any("registry" in a.name for a in node.names)
    assert ".enable(" not in src and ".grant(" not in src
    assert "Approval(" not in src


def test_invalid_request_id_controlled(tmp_path):
    for bad in (None, "", "   ", 123, "x" * 513):
        rec = A.audit(bad, p7_path=tmp_path / "q.jsonl")
        assert rec.reason == "invalid-request-id"
        assert not rec.p7_present
