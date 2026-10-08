"""Tests identité visuelle : états, vérité, priorité, repli, sécurité."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from core.visual import adapter as _adapter
from core.visual.adapter import (
    adapt,
    from_mission_report,
    from_runtime_status,
    from_voice_report,
)
from core.visual.presence import render_ansi, render_json
from core.visual.states import (
    FUNDAMENTAL,
    HUMOROUS,
    MODES,
    VisualFrame,
    describe,
    frame_for,
    pick_state,
)


def test_etats_fondamentaux():
    assert len(FUNDAMENTAL) == 12
    for etat in FUNDAMENTAL:
        frame = frame_for(etat)
        assert frame.etat == etat
        assert frame.yeux.expression
        assert frame.bouche.expression
        assert 0.0 <= frame.noyau.luminosite <= 1.0
    assert frame_for("INCONNU").etat == "IDLE"


def test_transitions_sequence():
    assert adapt({}).etat == "IDLE"
    assert adapt({"ecoute_en_cours": True}).etat == "LISTENING"
    assert adapt({"reflexion_en_cours": True}).etat == "THINKING"
    assert adapt({"parole_en_cours": True}).etat == "SPEAKING"
    assert adapt({"execution_en_cours": True}).etat == "EXECUTING"
    assert adapt({"verification_en_cours": True}).etat == "VERIFYING"
    assert adapt({"interrompu": True}).etat == "INTERRUPTED"


def test_priorite_operational():
    frame = adapt({"ecoute_en_cours": True, "parole_en_cours": True,
                   "attente_approbation": True, "execution_en_cours": True,
                   "erreur_reelle": True})
    assert frame.etat == "ERROR"
    assert adapt({"attente_approbation": True,
                  "execution_en_cours": True}).etat == "WAITING_APPROVAL"
    assert adapt({"verification": "VERIFIED_SUCCESS",
                  "parole_en_cours": True}).etat == "SUCCESS"
    assert pick_state(["IDLE", "SPEAKING", "LISTENING"]) == "SPEAKING"


def test_attente_approbation_jamais_succes():
    frame = adapt({"attente_approbation": True})
    assert frame.etat == "WAITING_APPROVAL"
    assert "autorise" not in frame.raison.lower()


def test_succes_apres_verification_uniquement():
    assert adapt({"verification": "VERIFIED_SUCCESS"}).etat == "SUCCESS"
    assert adapt({"verification": "VERIFIED_FAILURE"}).etat == "UNCERTAIN"
    assert adapt({"execution_en_cours": True}).etat == "EXECUTING"


def test_erreur_reelle():
    frame = adapt({"erreur_reelle": True})
    assert frame.etat == "ERROR"
    assert frame.noyau.anneaux_synchronises is False


def test_incertitude():
    assert adapt({"incertitude_reelle": True}).etat == "UNCERTAIN"
    frame = adapt({"incertitude_reelle": True})
    assert frame.yeux.asymetrie is True


def test_interruption():
    assert adapt({"interrompu": True}).etat == "INTERRUPTED"


def test_mode_contextuel_identite_preservee():
    frame = adapt({"mode": "TRANSLATION", "ecoute_en_cours": True})
    assert frame.mode == "TRANSLATION"
    assert frame.etat == "LISTENING"
    assert frame.yeux.expression == "ouverts-attentifs"


def test_mode_humoristique_contexte_grave_refuse():
    frame = adapt({"mode": "SECRET"})
    assert frame.mode == ""
    assert "ludique" in frame.raison
    frame = adapt({"mode": "SECRET", "contexte_ludique": True})
    assert frame.mode == "SECRET"


def test_repli_sans_terminal():
    frame = frame_for("SUCCESS")
    data = json.loads(render_json(frame))
    assert data["etat"] == "SUCCESS"
    assert data["yeux"]["expression"] == "grands-ouverts"
    assert render_json("pas-une-frame") == "{}"
    assert render_ansi("pas-une-frame") == ""


def test_arret_redemarrage_sans_residu():
    first = adapt({"parole_en_cours": True})
    assert first.etat == "SPEAKING"
    idle = adapt({})
    assert idle.etat == "IDLE" and idle.mode == ""
    assert render_ansi(first, 3) == render_ansi(first, 3)
    assert isinstance(render_ansi(first, 0), str)


def test_runtime_ne_bloque_pas():
    import time
    frame = adapt({"ecoute_en_cours": True})
    start = time.monotonic()
    for tick in range(20):
        render_ansi(frame, tick)
        render_json(frame)
    assert time.monotonic() - start < 5.0


def test_autorisation_inchangee():
    for name in ("core/visual/states.py", "core/visual/adapter.py",
                 "core/visual/presence.py"):
        src = Path(name).read_text(encoding="utf-8")
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
        assert froms <= {"__future__", "dataclasses", "typing", "json",
                         "core.visual.states"}, (name, froms)
        assert not (called & {"invoke", "approve_confirmation",
                              "submit_turn", "resolve_confirmation",
                              "ApprovalGate", "MandateRegistry"}), \
            (name, called)
    assert "taios" not in Path("core/visual/adapter.py").read_text(
        encoding="utf-8").lower()


def test_integration_runtime_reelle(tmp_path):
    from core.runtime.config import RuntimeConfig
    from core.runtime.lifecycle import create_runtime
    cfg = RuntimeConfig(data_dir=str(tmp_path / "d"), session_id="s-vis")
    ok, runtime = create_runtime(cfg)
    assert ok is True
    try:
        frame = from_runtime_status(runtime.status())
        assert frame.etat == "IDLE"
    finally:
        runtime.stop()


def test_integration_voix_mission_reelles():
    from core.voice.voice_loop import VoiceTurnReport
    voice = VoiceTurnReport(stage="termine", core="CONFIRM_CREATED",
                            tts="ok")
    assert from_voice_report(voice).etat == "WAITING_APPROVAL"

    class MissionReport:
        etat_final = "COMPLETED"

        class Item:
            verification = "VERIFIED_SUCCESS"
        rapports = (Item(),)

    assert from_mission_report(MissionReport()).etat == "SUCCESS"

    class BadMission:
        etat_final = "FAILED"
        rapports = ()
    assert from_mission_report(BadMission()).etat == "ERROR"
