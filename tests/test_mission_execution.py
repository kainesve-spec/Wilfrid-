"""Tests exécution de missions : orchestration gouvernée, sans autorité."""

from __future__ import annotations

import ast
from pathlib import Path

from core.mission.execution import (
    CAPABILITY_TO_TOOL,
    describe,
    execute_mission,
    execute_task,
)
from core.mission.mission import create_mission, refresh_ready
from core.p7.approval_gate import ApprovalGate
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.resolver import jail_root

ROOT = jail_root()


def _mission(tasks, **over):
    params = dict(mission_id="m-test", objective="objectif-test",
                  tasks=tasks,
                  allowed_capabilities=("P7.CATALOG_READ",
                                        "P7.NOTIFY_LOCAL"),
                  provenance="test")
    params.update(over)
    ok, mission = create_mission(**params)
    assert ok is True, mission
    ok, mission = __import__("core.mission.mission", fromlist=["x"]) \
        .transition_mission(mission, "ACTIVE")
    assert ok is True
    return refresh_ready(mission)


def test_mission_informative():
    mission = _mission([{"id": "t1", "objective": "lire la consigne"}])
    gate = ApprovalGate()
    journal = Journal(path=":memory:")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0, decisions={})
    assert report.etat_final == "terminee"
    assert report.executee is False
    assert report.autorisation == "sans-objet-information"
    assert Registry().active_count() == 0


def test_action_reversible_approuvee(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("APPROVE", "Monsieur K")},
        tool_params={"t1": {"message": "mission-test"}},
        payloads={}, request_id="m-reversible")
    assert report.etat_final == "terminee", report
    assert report.executee is True
    assert "Monsieur K" in report.autorisation
    assert report.verification == "VERIFIED_SUCCESS"
    for leftover in (ROOT / "notifications").glob("m-*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def test_approbation_refusee(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    before = sorted((ROOT / "notifications").iterdir())
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("DENY", "Monsieur K")},
        tool_params={"t1": {"message": "ne-pas-executer"}})
    assert report.etat_final == "echouee"
    assert report.executee is False
    assert sorted((ROOT / "notifications").iterdir()) == before


def test_approbation_expiree(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=5000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("APPROVE", "Monsieur K", 1000.5)},
        tool_params={"t1": {"message": "perime"}})
    assert report.etat_final in ("echouee", "refusee")
    assert report.executee is False


def test_outil_indisponible(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "chose impossible",
          "required_capability": "P7.CAPACITE_INCONNUE"}],
        allowed_capabilities=("P7.CAPACITE_INCONNUE",))
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("APPROVE", "Monsieur K")})
    assert report.etat_final == "bloquee"
    assert report.executee is False
    assert Registry().active_count() == 0


def test_echec_execution(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "lire sans nom",
          "required_capability": "P7.JAIL_READ"}],
        allowed_capabilities=("P7.JAIL_READ",))
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("APPROVE", "Monsieur K")},
        tool_params={"t1": {}})
    assert report.etat_final == "echouee"
    assert report.executee is False


def test_verification_documentee(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "lire catalogue",
          "required_capability": "P7.CATALOG_READ"}],
        allowed_capabilities=("P7.CATALOG_READ",))
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0,
        decisions={"t1": ("APPROVE", "Monsieur K")},
        tool_params={"t1": {}})
    assert report.verification in ("VERIFIED_SUCCESS", "VERIFIED_FAILURE",
                                   "UNCERTAIN", "sans-objet")
    if report.verification == "VERIFIED_SUCCESS":
        assert report.etat_final == "terminee"
    else:
        assert report.incertitude != "" or report.etat_final != "terminee"


def test_double_appel_refuse(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    params = {"tool_params": {"t1": {"message": "une-fois"}},
              "decisions": {"t1": ("APPROVE", "Monsieur K")}}
    mission, first = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0, request_id="m-double", **params)
    assert first.etat_final == "terminee"
    mission, second = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1001.0,
        session_id="s", turn_index=1, request_id="m-double", **params)
    assert second.etat_final == "refusee"
    assert second.executee is False
    for leftover in (ROOT / "notifications").glob("m-*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def test_interruption_reprise(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, paused = execute_mission(
        mission, gate=gate, journal=journal, now=1000.0, session_id="s",
        decisions={}, tool_params={"t1": {"message": "reprise"}},
        request_id="m-reprise")
    assert paused.etat_final == "PAUSED"
    assert paused.raison == "en-attente-approbation"
    mission, done = execute_mission(
        mission, gate=gate, journal=journal, now=1001.0, session_id="s",
        decisions={"t1": ("APPROVE", "Monsieur K")},
        tool_params={"t1": {"message": "reprise"}},
        request_id="m-reprise")
    assert done.etat_final == "COMPLETED", done
    assert done.plan == (("t1", "COMPLETED"),)
    for leftover in (ROOT / "notifications").glob("m-*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def test_cloture_correcte(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "lire consigne"},
         {"id": "t2", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL",
          "dependencies": ["t1"]}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_mission(
        mission, gate=gate, journal=journal, now=1000.0, session_id="s",
        decisions={"t2": ("APPROVE", "Monsieur K")},
        tool_params={"t2": {"message": "cloture"}},
        request_id="m-cloture")
    assert report.etat_final == "COMPLETED", report
    assert len(report.rapports) == 2
    for leftover in (ROOT / "notifications").glob("m-*"):
        try:
            leftover.unlink(missing_ok=True)
        except OSError:
            pass


def test_voix_ne_vaut_pas_approbation(tmp_path):
    mission = _mission(
        [{"id": "t1", "objective": "notifier",
          "required_capability": "P7.NOTIFY_LOCAL"}])
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    before = sorted((ROOT / "notifications").iterdir())
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0,
        session_id="s", turn_index=0, decisions={},
        tool_params={"t1": {"message": "oui, approuve"}})
    assert report.executee is False
    assert gate.audit() == []
    assert sorted((ROOT / "notifications").iterdir()) == before
    assert Registry().active_count() == 0


def test_execution_sans_autorite():
    src = Path("core/mission/execution.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set = set()
    froms: set = set()
    called: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
            froms.add(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    assert not (mods & {"socket", "urllib", "http", "requests", "subprocess",
                        "os", "sys"}), mods
    assert froms <= {"__future__", "dataclasses", "typing", "core.mission",
                      "core.mission.mission", "core.loop.loop",
                      "core.p7.tools"}, froms
    assert not (called & {"invoke", "approve_confirmation",
                          "deny_confirmation", "revoke", "suspend",
                          "PermissionRegistry", "ApprovalGate",
                          "MandateRegistry", "authorize_execution"}), called
    assert "taios" not in src.lower()
    assert CAPABILITY_TO_TOOL["P7.JAIL_READ"] == "jail.read"
    assert describe()["double-execution"] == "refusee"
