"""Wilfrid — providers IA via HTTP (sans SDK, sans autorité).

Chaque provider expose `complete()` : prompt minimisé → texte ou
erreur honnête. Secrets lus depuis l'environnement à l'appel (jamais
stockés, jamais journalisés). Sans credential : AUTH_REQUIRED.
Un provider ne peut ni approuver ni décider pour Wilfrid.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.agents.registry import Agent


@dataclass(frozen=True)
class AgentResult:
    """Issue d'appel : statut fermé + provenance, jamais d'invention."""

    status: str = "FAILED"
    agent_id: str = ""
    provider: str = ""
    model: str = ""
    text: str = ""
    detail: str = ""
    latency_s: float = 0.0


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str],
               timeout_s: float) -> Tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as reply:
            return int(reply.status), reply.read().decode(
                "utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(type(exc).__name__)


def _credential(agent: Agent) -> str:
    if not agent.auth_env:
        return ""
    return (os.environ.get(agent.auth_env) or "").strip()


def complete_openai(agent: Agent, prompt: str,
                    *, timeout_s: Any = None) -> AgentResult:
    """Chat Completions compatibles OpenAI (clé API requise)."""
    started = time.monotonic()
    key = _credential(agent)
    if not key:
        return AgentResult(status="AUTH_REQUIRED", agent_id=agent.id,
                           provider="OPENAI", model=agent.model,
                           detail="credential-absente")
    if not isinstance(prompt, str) or not prompt.strip():
        return AgentResult(status="INVALID", agent_id=agent.id,
                           provider="OPENAI", detail="prompt-invalide")
    endpoint = agent.endpoint or "https://api.openai.com/v1/chat/completions"
    try:
        status, body = _post_json(
            endpoint,
            {"model": agent.model or "gpt-4o-mini",
             "messages": [{"role": "user", "content": prompt.strip()}]},
            {"Authorization": "Bearer " + key,
             "Content-Type": "application/json"},
            float(timeout_s or agent.timeout_s))
    except RuntimeError as exc:
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OPENAI", detail="reseau:%s" % exc,
                           latency_s=time.monotonic() - started)
    try:
        data = json.loads(body)
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OPENAI", detail="reponse-invalide")
    if not isinstance(text, str) or not text.strip():
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OPENAI", detail="texte-vide")
    return AgentResult(status="SUCCESS", agent_id=agent.id,
                       provider="OPENAI", model=agent.model,
                       text=text.strip()[:8000], detail="ok",
                       latency_s=time.monotonic() - started)


def complete_gemini(agent: Agent, prompt: str,
                   *, timeout_s: Any = None) -> AgentResult:
    """Gemini generateContent (clé API requise)."""
    started = time.monotonic()
    key = _credential(agent)
    if not key:
        return AgentResult(status="AUTH_REQUIRED", agent_id=agent.id,
                           provider="GEMINI", model=agent.model,
                           detail="credential-absente")
    if not isinstance(prompt, str) or not prompt.strip():
        return AgentResult(status="INVALID", agent_id=agent.id,
                           provider="GEMINI", detail="prompt-invalide")
    endpoint = agent.endpoint or \
        "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % (
            agent.model or "gemini-2.0-flash")
    try:
        status, body = _post_json(
            endpoint + "?key=" + key,
            {"contents": [{"parts": [{"text": prompt.strip()}]}]},
            {"Content-Type": "application/json"},
            float(timeout_s or agent.timeout_s))
    except RuntimeError as exc:
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="GEMINI", detail="reseau:%s" % exc,
                           latency_s=time.monotonic() - started)
    try:
        data = json.loads(body)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (ValueError, KeyError, IndexError, TypeError):
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="GEMINI", detail="reponse-invalide")
    if not isinstance(text, str) or not text.strip():
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="GEMINI", detail="texte-vide")
    return AgentResult(status="SUCCESS", agent_id=agent.id,
                       provider="GEMINI", model=agent.model,
                       text=text.strip()[:8000], detail="ok",
                       latency_s=time.monotonic() - started)


def complete_claude(agent: Agent, prompt: str,
                   *, timeout_s: Any = None) -> AgentResult:
    """Claude Messages (clé API requise)."""
    started = time.monotonic()
    key = _credential(agent)
    if not key:
        return AgentResult(status="AUTH_REQUIRED", agent_id=agent.id,
                           provider="CLAUDE", model=agent.model,
                           detail="credential-absente")
    if not isinstance(prompt, str) or not prompt.strip():
        return AgentResult(status="INVALID", agent_id=agent.id,
                           provider="CLAUDE", detail="prompt-invalide")
    endpoint = agent.endpoint or "https://api.anthropic.com/v1/messages"
    try:
        status, body = _post_json(
            endpoint,
            {"model": agent.model or "claude-3-5-haiku-latest",
             "max_tokens": 1024,
             "messages": [{"role": "user", "content": prompt.strip()}]},
            {"x-api-key": key, "anthropic-version": "2023-06-01",
             "Content-Type": "application/json"},
            float(timeout_s or agent.timeout_s))
    except RuntimeError as exc:
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="CLAUDE", detail="reseau:%s" % exc,
                           latency_s=time.monotonic() - started)
    try:
        data = json.loads(body)
        text = "".join(block.get("text", "") for block in data["content"]
                       if isinstance(block, dict))
    except (ValueError, KeyError, TypeError):
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="CLAUDE", detail="reponse-invalide")
    if not text.strip():
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="CLAUDE", detail="texte-vide")
    return AgentResult(status="SUCCESS", agent_id=agent.id,
                       provider="CLAUDE", model=agent.model,
                       text=text.strip()[:8000], detail="ok",
                       latency_s=time.monotonic() - started)


def complete_omniroute(agent: Agent, prompt: str,
                       *, timeout_s: Any = None) -> AgentResult:
    """OmniRoute local OpenAI-compatible (clé locale requise)."""
    started = time.monotonic()
    key = _credential(agent)
    if not key:
        return AgentResult(status="AUTH_REQUIRED", agent_id=agent.id,
                           provider="OMNIROUTE", model=agent.model,
                           detail="credential-absente")
    if not isinstance(prompt, str) or not prompt.strip():
        return AgentResult(status="INVALID", agent_id=agent.id,
                           provider="OMNIROUTE", detail="prompt-invalide")
    endpoint = (agent.endpoint or "http://localhost:20128") + \
        "/v1/chat/completions"
    try:
        status, body = _post_json(
            endpoint,
            {"model": agent.model or "default",
             "messages": [{"role": "user", "content": prompt.strip()}]},
            {"Authorization": "Bearer " + key,
             "Content-Type": "application/json"},
            float(timeout_s or agent.timeout_s))
    except RuntimeError as exc:
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OMNIROUTE", detail="reseau:%s" % exc,
                           latency_s=time.monotonic() - started)
    if status == 401:
        return AgentResult(status="AUTH_REQUIRED", agent_id=agent.id,
                           provider="OMNIROUTE",
                           detail="cle-refusee-401")
    try:
        data = json.loads(body)
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OMNIROUTE", detail="reponse-invalide")
    if not isinstance(text, str) or not text.strip():
        return AgentResult(status="FAILED", agent_id=agent.id,
                           provider="OMNIROUTE", detail="texte-vide")
    return AgentResult(status="SUCCESS", agent_id=agent.id,
                       provider="OMNIROUTE", model=agent.model,
                       text=text.strip()[:8000], detail="ok",
                       latency_s=time.monotonic() - started)


COMPLETERS = {"OPENAI": complete_openai, "GEMINI": complete_gemini,
              "CLAUDE": complete_claude, "OMNIROUTE": complete_omniroute}
