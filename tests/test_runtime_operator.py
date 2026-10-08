"""Tests interface opérateur : commandes humaines explicites, sans autorité."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.runtime.config import RuntimeConfig
from core.runtime.lifecycle import create_runtime
from core.runtime.operator import OPERATOR_COMMANDS, handle_command


def _runtime(tmp_path, session="s-op"):
    cfg = RuntimeConfig(data_dir=str(tmp_path / "d"), session_id=session)
    ok, runtime = create_runtime(cfg)
    assert ok is True
    ok, _ = runtime.begin_running()
    assert ok is True
    return runtime


def test_commandes_inconnues_et_passthrough():
    handled, _ = handle_command(None, "Bonjour")
    assert handled is False
    handled, out = handle_command(None, "/inexistante")
    assert handled is True and "commande-inconnue" in out


def test_status_pending_vides(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        handled, out = handle_command(runtime, "/status")
        assert handled is True and "etat=RUNNING" in out
        handled, out = handle_command(runtime, "/pending")
        assert handled is True and out == "aucune-demande-en-attente"
        handled, out = handle_command(runtime, "/approve")
        assert handled is True and out == "aucune-demande-en-attente"
        handled, out = handle_command(runtime, "/missions")
        assert handled is True and out == "aucune-mission"
    finally:
        runtime.stop()


def test_approve_deny_session(tmp_path):
    from core.p7.resolver import ensure_jail, jail_root
    ok, _, _ = ensure_jail()
    assert ok
    target = jail_root() / "op_notes"
    target.write_bytes(b"notes-operateur")
    try:
        runtime = _runtime(tmp_path)
        try:
            done, result = runtime.run_turn("Lis le fichier op_notes")
            assert done is True and result.kind == "CONFIRM_CREATED"
            handled, out = handle_command(runtime, "/pending")
            assert handled is True and "P7.JAIL_READ" in out
            handled, out = handle_command(runtime, "/deny", now=1000.0)
            assert handled is True
            assert out.startswith("resultat: REFUSED")
            done, result = runtime.run_turn("Lis le fichier op_notes")
            assert done is True and result.kind == "CONFIRM_CREATED"
            handled, out = handle_command(runtime, "/approve", now=1000.0)
            assert handled is True
            assert "approuve-execute-verifie" in out
        finally:
            runtime.stop()
    finally:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def test_mission_cycle_operateur(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        handled, out = handle_command(
            runtime, '/mnew {"id": "m1", "objective": "notifier", '
            '"tasks": [{"id": "t1", "objective": "notifier", '
            '"required_capability": "P7.NOTIFY_LOCAL", '
            '"params": {"message": "m1-t1"}}], '
            '"allowed_capabilities": ["P7.NOTIFY_LOCAL"]}')
        assert handled is True and out == "mission-creee: m1", out
        handled, out = handle_command(runtime, "/missions")
        assert handled is True and "m1=" in out
        handled, out = handle_command(runtime, "/mshow m1")
        assert handled is True and "t1:" in out
        handled, out = handle_command(runtime, "/mrun m1", now=1000.0)
        assert handled is True and "PAUSED" in out
        handled, out = handle_command(
            runtime, "/mrun m1 APPROVE:t1", now=1001.0)
        assert handled is True and "COMPLETED" in out, out
    finally:
        runtime.stop()
        from core.p7.resolver import jail_root as _jail_root
        for leftover in (_jail_root() / "notifications").glob("run-m1-*"):
            try:
                leftover.unlink(missing_ok=True)
            except OSError:
                pass


def test_mission_json_invalide(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        handled, out = handle_command(runtime, "/mnew pas-json")
        assert handled is True and out == "json-invalide"
        handled, out = handle_command(runtime, "/mshow inconnu")
        assert handled is True and out == "mission-introuvable"
        handled, out = handle_command(runtime, "/mrun inconnu")
        assert handled is True
    finally:
        runtime.stop()


def test_voix_sans_commande_operateur():
    src = Path("core/voice/voice_loop.py").read_text(encoding="utf-8")
    assert "operator" not in src
    assert "handle_command" not in src
    src = Path("core/voice/audio_live.py").read_text(encoding="utf-8")
    assert "operator" not in src


def test_repl_approve_bout_en_bout(tmp_path):
    script = ("Lis le fichier notes\n/pending\n/deny\n/status\n")
    proc = subprocess.run(
        [sys.executable, "wilfrid.py", "--data-dir",
         str(tmp_path / "d"), "--session-id", "s-opreel",
         "--max-turns", "10"],
        input=script, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert "Confirmation requise" in proc.stdout
    assert "P7.JAIL_READ" in proc.stdout
    assert "resultat: REFUSED" in proc.stdout
    assert "etat=RUNNING" in proc.stdout
