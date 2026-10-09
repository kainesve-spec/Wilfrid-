"""Tests application locale : chat/voix persistants, sans autorité."""

from __future__ import annotations

import ast
import io
import json
import wave
from pathlib import Path

from core.runtime.config import RuntimeConfig
from core.runtime.lifecycle import create_runtime
from core.visual.app import PAGE_CHAT, WilfridApp
from core.visual.server import VisualServer


def _app(tmp_path, session="s-app"):
    cfg = RuntimeConfig(data_dir=str(tmp_path / "d"), session_id=session)
    ok, runtime = create_runtime(cfg)
    assert ok is True
    ok, _ = runtime.begin_running()
    assert ok is True
    return runtime, WilfridApp(runtime)


def test_chat_bout_en_bout(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        code, payload, ctype = app.handle(
            "/api/chat", json.dumps({"text": "Bonjour"}).encode("utf-8"))
        assert code == 200 and ctype == "application/json"
        data = json.loads(payload.decode("utf-8"))
        assert "Bien reçu" in data["answer"]
        assert data["kind"] == "RESPONDED"
        code, payload, _ = app.handle("/", b"")
        assert code == 200 and b"Wilfrid" in payload
        assert "mediaDevices" in payload.decode("utf-8")
    finally:
        runtime.stop()


def test_continuite_session(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        app.handle("/api/chat", json.dumps(
            {"text": "Monsieur K aime le thé."}).encode("utf-8"))
        code, payload, _ = app.handle(
            "/api/chat", json.dumps({"text": "Bonjour"}).encode("utf-8"))
        assert code == 200
        from core.memory.continuity import recall_context
        ctx = recall_context(runtime._memory, session_id="s-app")
        assert any("thé" in c.get("text", "") for c in ctx)
    finally:
        runtime.stop()


def test_voix_bout_en_bout(tmp_path):
    import base64
    runtime, app = _app(tmp_path)
    try:
        with wave.open("tests/data/stt_fr_naturel.wav", "rb") as handle:
            frames = handle.readframes(handle.getnframes())
        code, payload, _ = app.handle(
            "/api/voice", json.dumps(
                {"pcm_b64": base64.b64encode(frames).decode("ascii")}
            ).encode("utf-8"))
        assert code == 200
        data = json.loads(payload.decode("utf-8"))
        assert data["text"].strip() != ""
        assert data["answer"].strip() != ""
        assert data["audio_b64"].strip() != ""
        raw = base64.b64decode(data["audio_b64"])
        assert raw[:4] == b"RIFF"
    finally:
        runtime.stop()


def test_pas_de_route_approbation(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        for path in ("/approve", "/deny", "/api/approve", "/admin",
                      "/exec"):
            assert app.handle(path, b"")[0] == 404
    finally:
        runtime.stop()


def test_entrees_invalides(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        assert app.handle("/api/chat", b"pas-json")[0] == 400
        assert app.handle("/api/chat", json.dumps(
            {"text": "   "}).encode("utf-8"))[0] == 400
        assert app.handle("/api/voice", json.dumps(
            {"pcm_b64": "!!!"}).encode("utf-8"))[0] == 400
        assert app.handle("/inexistant", b"")[0] == 404
    finally:
        runtime.stop()


def test_serveur_app_bout_en_bout(tmp_path):
    import urllib.request
    runtime, app = _app(tmp_path)
    server = VisualServer(app=app, port=0)
    try:
        ok, _ = server.start()
        assert ok is True
        base = "http://127.0.0.1:%d" % server.port
        with urllib.request.urlopen(base + "/", timeout=10) as reply:
            assert reply.status == 200
        data = json.dumps({"text": "Bonjour"}).encode("utf-8")
        request = urllib.request.Request(
            base + "/api/chat", data=data,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as reply:
            assert reply.status == 200
            assert "Bien reçu" in reply.read().decode("utf-8")
    finally:
        server.stop()
        runtime.stop()
    assert server.running() is False


def test_app_sans_autorite():
    for name in ("core/visual/app.py",):
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
        assert not (called & {"invoke", "approve_confirmation",
                              "submit_turn", "resolve_confirmation",
                              "ApprovalGate", "system", "popen"}), \
            (name, called)
        lowered = src.lower()
        assert "taios" not in lowered, name
        assert "sk-" not in src, name
        assert "approve" not in lowered or "approbations" in lowered, name
    assert "mediaDevices" in PAGE_CHAT


def test_snapshot_fraicheur_definie(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        code, payload, _ = app.handle("/snapshot", b"")
        assert code == 200
        data = json.loads(payload.decode("utf-8"))
        assert data["fraicheur"].strip() != ""
        assert "undefined" not in json.dumps(data)
        assert isinstance(data["age_s"], (int, float))
    finally:
        runtime.stop()


def test_png_requete_bloque_cache(tmp_path):
    runtime, app = _app(tmp_path)
    try:
        for path in ("/png", "/png?tick=123456", "/png?t=1&t=2"):
            code, payload, ctype = app.handle(path, b"")
            assert code == 200, path
            assert payload[:8] == b"\x89PNG\r\n\x1a\n"
            assert ctype == "image/png"
    finally:
        runtime.stop()
