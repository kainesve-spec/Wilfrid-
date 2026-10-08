"""Tests capacités Android : registre, gouvernance, mocks, zéro effet réel."""

from __future__ import annotations

import ast
from pathlib import Path

from core.android.adapters.termux_api import (
    ALLOWLIST,
    TermuxResult,
    describe as adapter_describe,
    run_command,
)
from core.android.capabilities import (
    AndroidRegistry,
    SENSITIVE_IDS,
    default_registry,
    describe,
)
from core.android.execution import execute_capability
from core.p7.approval_gate import ApprovalGate
from core.p7.journal import Journal
from core.p7.registry import Registry


def _fake_run(result):
    def fake(command, args=None):
        return result
    return fake


def test_registre_declaratif():
    registry = default_registry()
    ids = [c.id for c in registry.list()]
    assert len(ids) == 16
    assert "BATTERY_STATUS" in ids and "SMS_SEND" in ids
    assert registry.exists("AUDIO_INFO") is True
    assert registry.exists("FAUSSE_CAPACITE") is False
    assert registry.get(None) is None
    assert describe()["default_deny"] is True
    assert set(adapter_describe()["commandes"]) == set(ALLOWLIST)


def test_etats_et_risques():
    registry = default_registry()
    states = {c.etat for c in registry.list()}
    assert "AVAILABLE" in states and "AVAILABLE_WITH_PERMISSION" in states
    for sensitive in SENSITIVE_IDS:
        cap = registry.get(sensitive)
        assert cap is not None
        assert cap.risque in ("modere", "sensible", "critique")
        assert cap.confirmation_requise is True


def test_grant_revoke():
    registry = default_registry()
    assert registry.granted("BATTERY_STATUS") is True
    assert registry.granted("SMS_SEND") is False
    ok, granted = registry.grant("SMS_SEND", "Monsieur K")
    assert ok is True and granted.granted("SMS_SEND") is True
    assert registry.granted("SMS_SEND") is False
    ok, revoked = granted.revoke("SMS_SEND")
    assert ok is True and revoked.granted("SMS_SEND") is False
    assert registry.grant("INCONNUE", "Monsieur K")[0] is False
    assert registry.grant("SMS_SEND", "")[0] is False
    assert registry.revoke("JAMAIS_ACCORDEE")[0] is False


def test_autorisation_absente(tmp_path):
    registry = default_registry()
    journal = Journal(path=tmp_path / "j.jsonl")
    result = execute_capability(
        registry, "SMS_SEND", ["+33600000000", "bonjour"], gate=None,
        journal=journal, now=1000.0)
    assert result.status == "DENIED"
    assert result.success is False


def test_capabilite_inconnue(tmp_path):
    registry = default_registry()
    journal = Journal(path=tmp_path / "j.jsonl")
    result = execute_capability(
        registry, "RM_RF_TOUT", [], gate=ApprovalGate(),
        journal=journal, now=1000.0,
        run_fn=_fake_run(TermuxResult(status="SUCCESS")))
    assert result.status == "UNKNOWN"
    assert result.success is False


def test_execution_reelle_inoffensive(tmp_path):
    # Appel réel inoffensif ; le daemon Termux:API peut être lent :
    # TIMEOUT/UNAVAILABLE honnêtes acceptés, jamais simulés.
    registry = default_registry()
    journal = Journal(path=tmp_path / "j.jsonl")
    result = execute_capability(
        registry, "BATTERY_STATUS", [], gate=ApprovalGate(),
        journal=journal, now=1000.0)
    assert result.status in ("SUCCESS", "TIMEOUT", "UNAVAILABLE",
                             "FAILED"), result.error
    assert result.request_id.startswith("and-")
    if result.status == "SUCCESS":
        assert result.success is True
        assert isinstance(result.data, dict)
        assert "percentage" in result.data
        assert result.verification == "VERIFIED"


def test_confirmation_requise_bloque(tmp_path):
    ok, registry = default_registry().grant("OPEN_URL", "Monsieur K")
    assert ok is True
    journal = Journal(path=tmp_path / "j.jsonl")
    calls = []
    result = execute_capability(
        registry, "OPEN_URL", ["https://example.com"],
        gate=ApprovalGate(), journal=journal, now=1000.0,
        run_fn=lambda c, a=None: calls.append((c, a)) or
        TermuxResult(status="SUCCESS"))
    assert result.status == "BLOCKED"
    assert calls == []


def test_confirmation_puis_execution(tmp_path):
    ok, registry = default_registry().grant("OPEN_URL", "Monsieur K")
    assert ok is True
    journal = Journal(path=tmp_path / "j.jsonl")
    calls = []
    result = execute_capability(
        registry, "OPEN_URL", ["https://example.com"],
        gate=ApprovalGate(), journal=journal, now=1000.0,
        decisions={"OPEN_URL": ("APPROVE", "Monsieur K")},
        run_fn=lambda c, a=None: calls.append((c, a)) or
        TermuxResult(status="SUCCESS", command=c, returncode=0,
                     stdout="ok", reason="ok"))
    assert result.status == "SUCCESS", result.error
    assert calls == [("termux-open-url", ["https://example.com"])]


def test_refus_zero_effet(tmp_path):
    ok, registry = default_registry().grant("SMS_SEND", "Monsieur K")
    assert ok is True
    journal = Journal(path=tmp_path / "j.jsonl")
    calls = []
    result = execute_capability(
        registry, "SMS_SEND", ["+33600000000", "bonjour"],
        gate=ApprovalGate(), journal=journal, now=1000.0,
        decisions={"SMS_SEND": ("DENY", "Monsieur K")},
        run_fn=lambda c, a=None: calls.append(1) or
        TermuxResult(status="SUCCESS"))
    assert result.status == "DENIED"
    assert calls == []
    assert Registry().active_count() == 0


def test_requete_vocale_jamais_autorisation(tmp_path):
    ok, registry = default_registry().grant("TELEPHONY_CALL",
                                            "Monsieur K")
    assert ok is True
    journal = Journal(path=tmp_path / "j.jsonl")
    calls = []
    result = execute_capability(
        registry, "TELEPHONY_CALL", ["+33600000000"],
        gate=ApprovalGate(), journal=journal, now=1000.0, decisions={},
        run_fn=lambda c, a=None: calls.append(1) or
        TermuxResult(status="SUCCESS"))
    assert result.status == "BLOCKED"
    assert calls == []


def test_timeout_erreur_commande():
    assert run_command("COMMANDE_INCONNUE", []).status == "UNKNOWN_COMMAND"
    assert run_command("termux-battery-status", ["x"]).status == \
        "INVALID_ARGS"
    assert run_command("termux-sms-send", "+336").status == "INVALID_ARGS"
    assert run_command("termux-open-url", [""]).status == "INVALID_ARGS"
    assert run_command("termux-open-url", ["x" * 5000]).status == \
        "INVALID_ARGS"


def test_verification_echouee_honnete(tmp_path):
    registry = default_registry()
    journal = Journal(path=tmp_path / "j.jsonl")
    result = execute_capability(
        registry, "BATTERY_STATUS", [], gate=ApprovalGate(),
        journal=journal, now=1000.0,
        run_fn=_fake_run(TermuxResult(status="SUCCESS", stdout="vide")))
    assert result.status == "UNCERTAIN"
    assert result.success is False


def test_journal_provenance(tmp_path):
    import json
    registry = default_registry()
    path = tmp_path / "j.jsonl"
    journal = Journal(path=path)
    execute_capability(registry, "AUDIO_INFO", [], gate=ApprovalGate(),
                       journal=journal, now=1000.0,
                       run_fn=_fake_run(TermuxResult(
                           status="SUCCESS", stdout='{"a": 1}')))
    lines = [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    assert any(entry.get("request_id", "").startswith("and-")
               for entry in lines)


def test_securite_ast():
    for name in ("core/android/capabilities.py",
                 "core/android/execution.py",
                 "core/android/adapters/termux_api.py"):
        src = Path(name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        mods: set = set()
        called: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        assert not (mods & {"socket", "urllib", "http", "requests"}), \
            (name, mods)
        assert "shell=True" not in src, name
        assert not (called & {"invoke", "PermissionRegistry",
                              "MandateRegistry", "system", "popen",
                              "check_output",
                              "check_call"}), (name, called)
        lowered = src.lower()
        assert "taios" not in lowered, name
        assert "binance" not in lowered, name
    assert "sk-" not in Path(
        "core/android/execution.py").read_text(encoding="utf-8")
