"""Tests visualisation live : sink, vérité, serveur, isolation."""

from __future__ import annotations

import ast
import json
import threading
import urllib.request
from pathlib import Path

from core.visual import server as _server_mod
from core.visual.adapter import adapt
from core.visual.server import VisualServer, make_provider
from core.visual.sink import collect, describe as sink_describe, snapshot
from core.visual.states import frame_for


def test_sink_runtime():
    signals = collect()
    assert isinstance(signals, dict)
    runtime = type("R", (), {"state": "READY",
                             "status": lambda s: {}})()
    assert isinstance(collect(runtime=runtime), dict)


def test_sink_voix_mission_gate():
    from core.voice.voice_loop import VoiceTurnReport
    voice = VoiceTurnReport(stage="capture")
    assert collect(voice=voice)["ecoute_en_cours"] is True
    assert collect(gate_pending=object())["attente_approbation"] is True

    class MissionReport:
        etat_final = "PAUSED"
        rapports = ()
    assert collect(mission=MissionReport())["attente_approbation"] is True


def test_sink_internet_plugins_agents():
    class Net:
        status = "DNS_FAILED"
    assert collect(net=Net())["erreur_reelle"] is True

    class Net2:
        status = "CONTENT_VALIDATED"
    assert collect(net=Net2())["verification_en_cours"] is True

    class Plugin:
        state = "OPERATIONAL"
        proof = "exec-sure-ok"
    assert collect(plugin=Plugin())["verification"] == "VERIFIED_SUCCESS"

    class Plugin2:
        state = "DECLARED"
        proof = ""
    assert "verification" not in collect(plugin=Plugin2())

    class Agent:
        state = "CONFIGURED"
        proof = ""
    assert collect(agent=Agent())["reflexion_en_cours"] is True

    class Agent2:
        state = "FAILED"
        proof = ""
    assert collect(agent=Agent2())["erreur_reelle"] is True
    frame = snapshot(net=Net2(), mode="TRANSLATION")
    assert frame.etat == "VERIFYING"
    assert sink_describe()["ecritures"] == 0


def test_verite_execute_sans_verif():
    assert adapt({"execution_en_cours": True}).etat == "EXECUTING"
    assert adapt({"attente_approbation": True}).etat == "WAITING_APPROVAL"
    denied = adapt({"erreur_reelle": True})
    assert denied.etat == "ERROR"
    assert adapt({"verification": "UNCERTAIN"}).etat == "UNCERTAIN"
    assert adapt({"verification": "VERIFIED_SUCCESS"}).etat == "SUCCESS"


def test_serveur_cycle():
    server = VisualServer(port=0,
                          provider=make_provider(
                              lambda: frame_for("LISTENING"), tick=1))
    ok, _ = server.start()
    assert ok is True and server.running() is True
    base = "http://127.0.0.1:%d" % server.port
    with urllib.request.urlopen(base + "/health", timeout=5) as reply:
        assert reply.status == 200
    with urllib.request.urlopen(base + "/png", timeout=5) as reply:
        assert reply.status == 200
        assert reply.read()[:8] == b"\x89PNG\r\n\x1a\n"
    try:
        urllib.request.urlopen(base + "/commande", timeout=5)
        raise AssertionError("404 attendu")
    except Exception as exc:
        assert "404" in str(exc)
    assert server.snapshot()["requetes"] >= 3
    ok, _ = server.stop()
    assert ok is True and server.running() is False
    ok, _ = server.start()
    assert ok is True
    ok, _ = server.stop()
    assert ok is True
    json_server = VisualServer(
        port=0, provider=make_provider(lambda: frame_for("SUCCESS"),
                                       tick=1, fmt="json"))
    ok, _ = json_server.start()
    assert ok is True
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/snapshot" % json_server.port,
                timeout=5) as reply:
            assert reply.status == 200
            assert json.loads(reply.read())["etat"] == "SUCCESS"
    finally:
        json_server.stop()


def test_serveur_sans_provider():
    server = VisualServer(port=0, provider=None)
    ok, _ = server.start()
    assert ok is True
    try:
        base = "http://127.0.0.1:%d" % server.port
        try:
            urllib.request.urlopen(base + "/snapshot", timeout=5)
            raise AssertionError("503 attendu")
        except Exception as exc:
            assert "503" in str(exc)
    finally:
        server.stop()
    assert server.running() is False


def test_serveur_ne_bloque_pas_moteur():
    import time
    server = VisualServer(port=0,
                          provider=make_provider(
                              lambda: frame_for("IDLE"), tick=0,
                              fmt="json"))
    server.start()
    try:
        start = time.monotonic()
        total = 0
        for _ in range(5):
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/snapshot" % server.port,
                    timeout=5) as reply:
                total += len(reply.read())
        assert total > 0 and time.monotonic() - start < 15.0
    finally:
        server.stop()


def test_isolation_visuelle():
    for name in ("core/visual/sink.py", "core/visual/server.py"):
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
        assert not (mods & {"socket", "subprocess"}), (name, mods)
        assert "http" not in mods or "server" in name, (name, mods)
        assert not (called & {"invoke", "approve_confirmation",
                              "submit_turn", "resolve_confirmation",
                              "ApprovalGate", "system", "popen"}), \
            (name, called)
        lowered = src.lower()
        assert "taios" not in lowered, name
        assert "sk-" not in src, name


def test_threads_propres():
    before = len(threading.enumerate())
    server = VisualServer(port=0,
                          provider=make_provider(
                              lambda: frame_for("IDLE"), tick=0))
    server.start()
    server.stop()
    assert len(threading.enumerate()) <= before
