"""Tests runtime P0-1 : config, lifecycle, restart, offline, isolation."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from core.runtime.config import (
    RuntimeConfig,
    load_config,
    validate_config,
)
from core.runtime.lifecycle import WilfridRuntime, create_runtime
from core.runtime.main import run


def _cfg(tmp_path, **over):
    params = dict(data_dir=str(tmp_path / "data"),
                  session_id="s-test")
    params.update(over)
    return RuntimeConfig(**params)


def test_config_valide(tmp_path):
    ok, reason = validate_config(_cfg(tmp_path))
    assert ok is True, reason
    assert _cfg(tmp_path).resolved().memory_path.endswith("memory.sqlite")


def test_config_invalide(tmp_path):
    assert validate_config("pas-une-config")[0] is False
    assert validate_config(_cfg(tmp_path, session_id=""))[0] is False
    assert validate_config(_cfg(tmp_path, session_id="x" * 200))[0] is False
    assert validate_config(_cfg(tmp_path, max_turns=-1))[0] is False
    assert validate_config(_cfg(tmp_path, offline=False))[0] is False
    assert validate_config(_cfg(tmp_path, log_level="BRUIT"))[0] is False


def test_config_fichier_et_env(tmp_path, monkeypatch):
    target = tmp_path / "run.json"
    target.write_text(json.dumps({"session_id": "s-fichier",
                                  "max_turns": 3,
                                  "dictionary": {"TAIOS": "tayos"}}),
                      encoding="utf-8")
    loaded = load_config(target)
    assert loaded.session_id == "s-fichier"
    assert loaded.max_turns == 3
    assert loaded.dictionary == {"TAIOS": "tayos"}
    assert loaded.offline is True
    monkeypatch.setenv("WILFRID_SESSION_ID", "s-env")
    assert load_config(target).session_id == "s-env"
    assert load_config(tmp_path / "absent.json").session_id == "s-env"


def test_demarrage_ready(tmp_path):
    ok, runtime = create_runtime(_cfg(tmp_path))
    try:
        assert ok is True, runtime.error
        assert runtime.state == "READY"
        names = {c.name for c in runtime.components}
        assert {"memory", "knowledge", "p7", "session", "core"} <= names
    finally:
        runtime.stop()
    assert runtime.state == "STOPPED"


def test_erreur_init_sans_faux_ready(tmp_path):
    runtime = WilfridRuntime(config=_cfg(tmp_path, session_id=""))
    ok, reason = runtime.start()
    assert ok is False
    assert runtime.state in ("ERROR", "STOPPED")
    assert runtime.state != "READY"
    assert reason


def test_pas_de_double_init(tmp_path):
    ok, runtime = create_runtime(_cfg(tmp_path))
    assert ok is True
    try:
        ok, reason = runtime.start()
        assert ok is False and reason == "double-initialisation"
    finally:
        runtime.stop()


def test_arret_propre_idempotent(tmp_path):
    ok, runtime = create_runtime(_cfg(tmp_path))
    assert ok is True
    assert runtime.stop()[0] is True
    assert runtime.stop() == (True, "deja-arrete")
    assert runtime.state == "STOPPED"


def test_restart_propre(tmp_path):
    cfg = _cfg(tmp_path)
    ok, first = create_runtime(cfg)
    assert ok is True
    ok, _ = first.begin_running()
    assert ok is True
    ok, result = first.run_turn("Bonjour")
    assert ok is True and result.kind == "RESPONDED"
    assert first.stop()[0] is True
    ok, second = create_runtime(cfg)
    assert ok is True
    try:
        assert second.state == "READY"
        assert second.turn_count == 0
        ok, _ = second.begin_running()
        assert ok is True
        ok, result = second.run_turn("Bonjour")
        assert ok is True
    finally:
        second.stop()
    assert second.state == "STOPPED"


def test_run_turn_hors_running(tmp_path):
    ok, runtime = create_runtime(_cfg(tmp_path))
    assert ok is True
    try:
        done, reason = runtime.run_turn("Bonjour")
        assert done is False
    finally:
        runtime.stop()


def test_offline_sans_reseau():
    for name in ("core/runtime/config.py", "core/runtime/lifecycle.py",
                 "core/runtime/main.py"):
        src = Path(name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (mods & {"socket", "urllib", "http", "requests"}), \
            (name, mods)
        assert "elevenlabs" not in src.lower(), name


def test_isolation_taios():
    for name in ("core/runtime/config.py", "core/runtime/lifecycle.py",
                 "core/runtime/main.py", "wilfrid.py"):
        src = Path(name).read_text(encoding="utf-8").lower()
        assert "taios" not in src, name
        assert "qanxorus" not in src, name


def test_runtime_sans_autorite():
    src = Path("core/runtime/lifecycle.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    called: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    assert not (called & {"invoke", "approve_confirmation",
                          "deny_confirmation", "revoke", "suspend",
                          "authorize_execution", "resolve_confirmation",
                          "PermissionRegistry", "MandateRegistry"}), called


def test_lancement_reel(tmp_path):
    proc = subprocess.run(
        [sys.executable, "wilfrid.py", "--data-dir",
         str(tmp_path / "d"), "--session-id", "s-reel", "--max-turns", "1"],
        input="Bonjour\n", capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert "WILFRID READY session=s-reel" in proc.stdout
    assert "Wilfrid: Bien reçu." in proc.stdout
    assert "WILFRID STOPPED tours=1" in proc.stdout


def test_lancement_reel_erreur_config(tmp_path):
    target = tmp_path / "bad.json"
    target.write_text(json.dumps({"session_id": ""}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "wilfrid.py", "--config", str(target)],
        input="x\n", capture_output=True, text=True, timeout=120)
    assert proc.returncode == 3, (proc.returncode, proc.stderr[-300:])
    assert "WILFRID ERROR" in proc.stderr
