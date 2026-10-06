"""Tests vue statut P7 (lecture seule, faits bornés, 0 autorité)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from core.p7 import status as S
from core.p7.types import B2_IDS


def _snap(directory: Path) -> dict:
    state = {}
    for p in sorted(directory.rglob("*")):
        if p.is_symlink():
            state[str(p)] = "SYMLINK"
        elif p.is_file():
            state[str(p)] = (p.stat().st_size, p.stat().st_mtime_ns,
                             p.read_bytes())
        elif p.is_dir():
            state[str(p)] = "DIR"
    return state


def _jail(root: Path, *, channel: bool = True, backup: bool = True) -> Path:
    (root / "JAIL" / "P7").mkdir(parents=True, exist_ok=True)
    if channel:
        (root / "JAIL" / "P7" / "notifications").mkdir(parents=True,
                                                      exist_ok=True)
    if backup:
        (root / "JAIL" / "P7" / ".backup").mkdir(parents=True, exist_ok=True)
    return root / "JAIL" / "P7"


def test_nominal_snapshot(tmp_path):
    root = _jail(tmp_path)
    snap = S.status(active=0, declared=0, jail_root=root)
    assert snap.jail_present and snap.channel_present and snap.backup_present
    assert (snap.active, snap.declared) == (0, 0)
    assert snap.capabilities == tuple(B2_IDS) and len(snap.capabilities) == 4
    assert snap.reason == "ok"


def test_empty_registry():
    snap = S.status(active=0, declared=0,
                    jail_root="/nonexistent-xyz-123")
    assert (snap.active, snap.declared) == (0, 0)
    assert not snap.jail_present


def test_nonempty_registry_reported():
    snap = S.status(active=2, declared=5,
                    jail_root="/nonexistent-xyz-123")
    assert (snap.active, snap.declared) == (2, 5)


def test_active_declared_passthrough():
    assert S.status(active=0, declared=3,
                    jail_root="/nonexistent").declared == 3
    bad = S.status(active=-1, declared=0, jail_root="/nonexistent")
    assert bad.reason == "invalid-input"
    bad2 = S.status(active=True, declared=0, jail_root="/nonexistent")
    assert bad2.reason == "invalid-input"


def test_jail_present(tmp_path):
    root = _jail(tmp_path, channel=False, backup=False)
    snap = S.status(jail_root=root)
    assert snap.jail_present and not snap.channel_present
    assert not snap.backup_present


def test_jail_absent(tmp_path):
    snap = S.status(jail_root=tmp_path / "nope")
    assert not snap.jail_present and not snap.channel_present
    assert not snap.backup_present


def test_channel_present(tmp_path):
    root = _jail(tmp_path, backup=False)
    assert S.status(jail_root=root).channel_present


def test_backup_present(tmp_path):
    root = _jail(tmp_path, channel=False)
    assert S.status(jail_root=root).backup_present


def test_no_sensitive_content(tmp_path):
    secret = tmp_path / "JAIL" / "P7" / "notes.txt"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_bytes(b"top-secret-payload")
    snap = S.status(jail_root=tmp_path / "JAIL" / "P7")
    text = repr((snap.active, snap.declared, snap.jail_present,
                 snap.channel_present, snap.backup_present,
                 snap.capabilities, snap.reason))
    assert "top-secret" not in text and "notes.txt" not in text


def test_determinism(tmp_path):
    root = _jail(tmp_path)
    assert S.status(active=1, declared=2, jail_root=root) == \
        S.status(active=1, declared=2, jail_root=root)


def test_frozen_immutable():
    import dataclasses as _dc
    snap = S.status(jail_root="/nonexistent")
    try:
        snap.active = 9  # type: ignore[misc]
        raised = False
    except _dc.FrozenInstanceError:
        raised = True
    assert raised


def test_no_governor_approval_permission_activation():
    src = Path(__import__("core.p7.status", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "pathlib", "typing", "core"}
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    assert not (called & {"decide", "enable", "grant", "record", "write",
                          "mkdir", "unlink", "open", "socket", "Popen", "run"})
    assert "Approval(" not in src and "allow(" not in src.lower()


def test_no_network_subprocess():
    src = Path(__import__("core.p7.status", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"socket", "subprocess", "os", "sys", "webbrowser",
                        "requests", "urllib", "ftplib", "httpx", "ssl"})


def test_limited_paths_and_read_only(tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "data.bin").write_bytes(b"x" * 100)
    root = _jail(tmp_path)
    before = _snap(tmp_path)
    S.status(active=0, declared=0, jail_root=root)
    S.status(jail_root=tmp_path / "missing")
    assert _snap(tmp_path) == before


def test_default_root_no_crash():
    snap = S.status()
    assert isinstance(snap.jail_present, bool)
    assert snap.capabilities == tuple(B2_IDS)
