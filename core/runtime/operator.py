"""Wilfrid — interface opérateur (commandes humaines, sans autorité).

Seule interface par laquelle Monsieur K approuve/refuse et pilote les
missions : chaque commande explicite est tracée, aucune n'est implicite.
Toutes les autorisations passent par les mécanismes existants
(`resolve_live` pour la session, `execute_mission` + `decisions`
explicites pour les missions). La voix ne peut jamais approuver : ce
module n'est branché que sur l'entrée texte opérateur (REPL).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

OPERATOR_COMMANDS = ("/status", "/pending", "/approve", "/deny",
                     "/missions", "/mnew", "/mrun", "/mshow")


def _user_name() -> str:
    try:
        from core.session.identity import DEFAULT_USER_NAME
        name = str(DEFAULT_USER_NAME)
        return name if name.strip() else "Monsieur K"
    except Exception:
        return "Monsieur K"


def handle_command(runtime: Any, line: Any,
                   now: Any = None) -> Tuple[bool, str]:
    """Traite une commande `/...`. `(prise-en-charge, sortie-texte)`."""
    if not isinstance(line, str) or not line.strip().startswith("/"):
        return False, ""
    parts = line.strip().split(None, 1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""
    if command not in OPERATOR_COMMANDS:
        return True, "commande-inconnue (status/pending/approve/deny/" \
            "missions/mnew/mrun/mshow)"
    if command == "/status":
        return True, _status_text(runtime)
    if command == "/pending":
        return True, _pending_text(runtime)
    if command == "/approve":
        return True, _resolve_session(runtime, "APPROVE", now)
    if command == "/deny":
        return True, _resolve_session(runtime, "DENY", now)
    if command == "/missions":
        return True, _missions_text(runtime)
    if command == "/mshow":
        return True, _mission_show(runtime, argument)
    if command == "/mnew":
        return True, _mission_new(runtime, argument)
    if command == "/mrun":
        return True, _mission_run(runtime, argument, now)
    return True, "commande-inconnue"


def _status_text(runtime: Any) -> str:
    try:
        status = runtime.status()
    except Exception:
        return "etat-indisponible"
    parts = ["etat=%s tours=%d" % (status.get("state", "?"),
                                   status.get("turns", 0))]
    components = status.get("components", {})
    if isinstance(components, dict):
        down = sorted(name for name, info in components.items()
                      if isinstance(info, dict) and not info.get("ready"))
        parts.append("composants-ko=%s" % (",".join(down) if down else "aucun"))
    try:
        missions = runtime.list_missions()
        parts.append("missions=%d" % len(missions))
    except Exception:
        pass
    return " ".join(parts)


def _pending_text(runtime: Any) -> str:
    try:
        live = getattr(runtime, "_live", None)
        pending = getattr(live, "pending", None)
    except Exception:
        return "etant-indisponible"
    if pending is None:
        return "aucune-demande-en-attente"
    return "en-attente: %s sur %s (confirmation %s)" % (
        getattr(pending, "permission_id", "?"),
        getattr(pending, "target", "?"),
        getattr(pending, "confirmation_id", "?"))


def _resolve_session(runtime: Any, decision: str, now: Any) -> str:
    try:
        from core.loop.live import resolve_live
    except Exception:
        return "mecanisme-indisponible"
    live = getattr(runtime, "_live", None)
    gate = getattr(runtime, "_gate", None)
    journal = getattr(runtime, "_journal", None)
    if getattr(live, "pending", None) is None:
        return "aucune-demande-en-attente"
    moment = now if isinstance(now, (int, float)) else 0.0
    try:
        updated, result = resolve_live(gate, live, decision, _user_name(),
                                       now=moment, journal=journal)
    except Exception:
        return "resolution-impossible"
    try:
        runtime._live = updated
    except Exception:
        pass
    kind = str(getattr(result, "kind", ""))
    if kind == "CONFIRM_RESOLVED":
        return "approuve-execute-verifie: %s" % str(
            getattr(result, "verification", ""))
    return "resultat: %s %s" % (kind, str(getattr(result, "detail", "")))


def _missions_text(runtime: Any) -> str:
    try:
        missions = runtime.list_missions()
    except Exception:
        return "missions-indisponibles"
    if not missions:
        return "aucune-mission"
    return " ; ".join("%s=%s" % (mid, state)
                      for mid, state in missions)


def _mission_show(runtime: Any, argument: str) -> str:
    if not argument.strip():
        return "usage: /mshow <mission-id>"
    try:
        mission = runtime.get_mission(argument.strip())
    except Exception:
        return "mission-introuvable"
    if mission is None:
        return "mission-introuvable"
    tasks = getattr(mission, "tasks", ())
    return "mission %s etat=%s taches=%s" % (
        getattr(mission, "id", "?"), getattr(mission, "state", "?"),
        ",".join("%s:%s" % (getattr(t, "id", "?"),
                             getattr(t, "state", "?")) for t in tasks))


def _mission_new(runtime: Any, argument: str) -> str:
    if not argument.strip():
        return "usage: /mnew {\"id\": ..., \"objective\": ..., \"tasks\": [...]}"
    try:
        spec = json.loads(argument)
    except ValueError:
        return "json-invalide"
    try:
        ok, outcome = runtime.submit_mission(spec)
    except Exception:
        return "creation-impossible"
    if not ok:
        return "mission-refusee: %s" % str(outcome)[:80]
    return "mission-creee: %s" % str(outcome)


def _mission_run(runtime: Any, argument: str, now: Any) -> str:
    parts = argument.strip().split(None, 1)
    if not parts:
        return "usage: /mrun <mission-id> [APPROVE|DENY:<tache>]"
    moment = now if isinstance(now, (int, float)) else 0.0
    decisions: Dict[str, Any] = {}
    if len(parts) > 1:
        action, _, target = parts[1].partition(":")
        action = action.strip().upper()
        target = target.strip()
        if action in ("APPROVE", "DENY") and target:
            decisions[target] = (action, _user_name())
        else:
            return "decision-invalide (APPROVE|DENY:<tache>)"
    try:
        ok, report = runtime.run_mission(parts[0], decisions=decisions,
                                         now=moment)
    except Exception:
        return "execution-impossible"
    if not ok:
        return "mission-bloquee: %s" % str(report)[:120]
    lines = ["mission=%s etat=%s" % (report.mission_id, report.etat_final)]
    for item in report.rapports:
        lines.append("- %s: %s (autorisation=%s, verif=%s)" % (
            item.task_id, item.etat_final, item.autorisation,
            item.verification))
    if report.raison:
        lines.append("raison=%s" % report.raison)
    return "\n".join(lines)
