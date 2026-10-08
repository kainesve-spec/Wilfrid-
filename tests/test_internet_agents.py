"""Tests chantier 2 : internet, plugins, agents (mocks + preuves réelles)."""

from __future__ import annotations

import ast
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from core.agents.orchestration import (
    build_prompt,
    consult,
    consult_many,
    minimize_context,
)
from core.agents.providers import (
    complete_claude,
    complete_gemini,
    complete_omniroute,
    complete_openai,
)
from core.agents.registry import Agent, AgentRegistry, describe as reg_describe
from core.internet.engine import fetch_url
from core.internet.search import register_engine, search
from core.plugins.registry import Plugin, PluginRegistry


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/ok":
            body = b'{"hello": "monde"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/gros":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "9999999")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def _server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def test_engine_etapes_locales():
    httpd = _server()
    try:
        port = httpd.server_address[1]
        result = fetch_url("https://127.0.0.1:%d/ok" % port,
                           timeout_s=5.0)
        assert result.status == "DNS_FAILED"
        assert "ssrf" in result.detail
    finally:
        httpd.shutdown()


def test_engine_ssrf_bloque():
    result = fetch_url("https://localhost:9/x", timeout_s=3.0)
    assert result.status == "DNS_FAILED"
    assert "ssrf" in result.detail or "dns" in result.detail
    result = fetch_url("https://127.0.0.1:9/x", timeout_s=3.0)
    assert result.status == "DNS_FAILED"
    result = fetch_url("ftp://example.com/x")
    assert result.status == "DNS_FAILED"
    result = fetch_url("https://invalide.invalid/", timeout_s=5.0)
    assert result.status in ("DNS_FAILED", "CONNECTION_FAILED")


def test_engine_rejet_contenu():
    assert fetch_url("x" * 3000).status == "DNS_FAILED"


def test_search_indisponible_honnete():
    result = search("météo Paris")
    assert result.status == "SEARCH_UNAVAILABLE"
    assert result.results == ()
    assert register_engine("", None) is False


def test_plugins_cycle():
    registry = PluginRegistry()
    assert registry.declare(Plugin(id="demo", version="1.0"))[0] is True
    assert registry.declare(Plugin(id="demo"))[0] is False
    assert registry.transition("demo", "OPERATIONAL") == \
        (False, "transition-invalide")
    assert registry.transition("demo", "INSTALLED")[0] is True
    assert registry.transition("demo", "CONNECTED")[0] is True
    assert registry.transition("demo", "OPERATIONAL") == \
        (False, "preuve-requise")
    assert registry.transition("demo", "OPERATIONAL",
                                proof="exec-sure-ok")[0] is True
    assert registry.get("demo").state == "OPERATIONAL"
    assert registry.transition("demo", "CONNECTED") == \
        (False, "transition-invalide")
    assert [p.id for p in registry.list("OPERATIONAL")] == ["demo"]


def test_agents_etats():
    registry = AgentRegistry()
    assert registry.declare(Agent(
        id="o1", provider="OMNIROUTE",
        endpoint="http://localhost:20128",
        model="default", auth_env="WILFRID_TEST_KEY"))[0] is True
    assert registry.declare(Agent(
        id="bad", provider="INCONNU")) == \
        (False, "provider-inconnu")
    assert registry.transition("o1", "CONFIGURED") == \
        (False, "secret-absent")
    assert "OPENAI" in reg_describe()["providers"]


def test_providers_sans_credential(monkeypatch):
    monkeypatch.delenv("WILFRID_TEST_KEY", raising=False)
    agent = Agent(id="t", provider="OPENAI", model="m",
                  auth_env="WILFRID_TEST_KEY")
    assert complete_openai(agent, "bonjour").status == "AUTH_REQUIRED"
    assert complete_gemini(agent, "bonjour").status == "AUTH_REQUIRED"
    assert complete_claude(agent, "bonjour").status == "AUTH_REQUIRED"
    assert complete_omniroute(agent, "bonjour").status == "AUTH_REQUIRED"
    assert complete_openai(agent, "   ").status == "AUTH_REQUIRED"


def test_providers_succes_simule(monkeypatch):
    import core.agents.providers as providers
    monkeypatch.setenv("WILFRID_TEST_KEY", "cle-fausse-test")
    monkeypatch.setattr(
        providers, "_post_json",
        lambda url, payload, headers, timeout: (
            200, '{"choices": [{"message": {"content": "réponse test"}}]}'))
    agent = Agent(id="t", provider="OPENAI", model="m",
                  auth_env="WILFRID_TEST_KEY")
    result = complete_openai(agent, "bonjour")
    assert result.status == "SUCCESS"
    assert result.text == "réponse test"
    assert "cle-fausse-test" not in result.text


def test_omniroute_sante_reelle():
    import urllib.request
    with urllib.request.urlopen("http://localhost:20128/api/health",
                                timeout=10) as reply:
        data = json.loads(reply.read().decode("utf-8"))
    assert reply.status == 200 and data.get("status") == "ok"


def test_omniroute_auth_requise():
    agent = Agent(id="o", provider="OMNIROUTE",
                  endpoint="http://localhost:20128", model="default",
                  auth_env="WILFRID_ABSENT_XYZ")
    result = complete_omniroute(agent, "bonjour")
    assert result.status == "AUTH_REQUIRED"


def test_orchestration_agregee():
    registry = AgentRegistry()
    assert consult(registry, "inconnu", "q").status == "UNKNOWN"
    monkeys = minimize_context({"question": "q", "api_key": "x",
                                "souvenir": "y", "vide": ""})
    assert monkeys["forbidden"] == ["api_key"]
    assert "souvenir" in monkeys["sensitive"]
    assert monkeys["required"] == ["question"]
    prompt = build_prompt("Bonjour ?", {"question": "x", "api_key": "y"})
    assert "api_key" not in prompt and "Bonjour" in prompt


def test_secrets_jamais_exposes(monkeypatch):
    import core.agents.providers as providers
    monkeypatch.setenv("WILFRID_TEST_KEY", "cle-ultra-secrete-123")
    seen = {}

    def fake_post(url, payload, headers, timeout):
        seen.update(headers)
        return 200, '{"choices": [{"message": {"content": "ok"}}]}'

    monkeypatch.setattr(providers, "_post_json", fake_post)
    agent = Agent(id="t", provider="OPENAI", model="m",
                  auth_env="WILFRID_TEST_KEY")
    result = complete_openai(agent, "q")
    assert result.status == "SUCCESS"
    assert "cle-ultra-secrete-123" not in result.text
    assert "cle-ultra-secrete-123" not in result.detail
    assert seen.get("Authorization", "").startswith("Bearer ")
    for name in ("core/agents/providers.py", "core/agents/registry.py",
                 "core/agents/orchestration.py", "core/internet/engine.py",
                 "core/plugins/registry.py"):
        src = Path(name).read_text(encoding="utf-8")
        assert "sk-" not in src, name
        assert "sk_live" not in src, name
        tree = ast.parse(src)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        if "engine" in name:
            assert not (mods & {"subprocess", "requests", "httpx"}), \
                (name, mods)
        else:
            assert not (mods & {"socket", "subprocess", "requests",
                                "httpx"}), (name, mods)
        assert "taios" not in src.lower(), name


def test_mission_ressource_externe(tmp_path):
    from core.mission.execution import execute_task
    from core.mission.mission import (create_mission, refresh_ready,
                                      transition_mission)
    from core.p7.approval_gate import ApprovalGate
    from core.p7.journal import Journal
    ok, mission = create_mission(
        mission_id="m-ext", objective="consulter",
        tasks=[{"id": "t1", "objective": "lire avis externe"}],
        allowed_capabilities=())
    assert ok is True
    ok, mission = transition_mission(mission, "ACTIVE")
    assert ok is True
    mission = refresh_ready(mission)
    gate = ApprovalGate()
    journal = Journal(path=tmp_path / "j.jsonl")
    mission, report = execute_task(
        mission, "t1", gate=gate, journal=journal, now=1000.0)
    assert report.etat_final == "terminee"
    assert report.executee is False
