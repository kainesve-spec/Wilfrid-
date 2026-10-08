"""Wilfrid — exécution de missions (orchestration sans autorité).

Enchaîne le modèle existant (`mission.py`) avec les garde-fous existants
(`request_confirmation`/`resolve_confirmation` de `loop.py`, registre
d'outils pour la mise en forme). AUCUNE approbation créée ici : les
décisions humaines arrivent par le paramètre explicite `decisions`
(task_id → APPROVE/DENY). Sans décision : tâche bloquée, mission en
pause, reprise possible. Aucune exécution sans autorisation, aucune
double exécution (transitions terminales).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.mission import mission as _mission

CAPABILITY_TO_TOOL = {
    "P7.CATALOG_READ": "catalog.read",
    "P7.JAIL_READ": "jail.read",
    "P7.JAIL_WRITE_REVERSIBLE": "jail.write",
    "P7.NOTIFY_LOCAL": "notify.send",
}


@dataclass(frozen=True)
class TaskReport:
    """Rapport d'une tâche : demande, autorisation, effet, vérification."""

    task_id: str = ""
    demandee: str = ""
    autorisation: str = "absente"
    executee: bool = False
    resultat: str = ""
    verification: str = "sans-objet"
    incertitude: str = ""
    etat_final: str = ""


@dataclass(frozen=True)
class MissionReport:
    """Rapport de mission : plan, rapports, état final."""

    mission_id: str = ""
    plan: Tuple[Tuple[str, str], ...] = ()
    rapports: Tuple[TaskReport, ...] = ()
    etat_final: str = ""
    raison: str = ""


def _refresh(mission: Any) -> Any:
    try:
        return _mission.refresh_ready(mission)
    except Exception:
        return mission


def _set_task_state(mission: Any, task_id: str,
                    target: str) -> Tuple[bool, Any]:
    try:
        return _mission.transition_task(mission, task_id, target)
    except Exception:
        return False, "transition-impossible"


def _payload_for(call: Any, explicit: Any) -> Any:
    """Charge utile explicite, sinon dérivée des paramètres validés."""
    if explicit is not None:
        return explicit
    params = getattr(call, "params", {}) or {}
    if not isinstance(params, dict):
        return None
    if call.permission_id == "P7.JAIL_WRITE_REVERSIBLE":
        content = params.get("content")
        return bytes(content) if isinstance(content, (bytes, bytearray)) \
            else None
    if call.permission_id == "P7.NOTIFY_LOCAL":
        message = params.get("message")
        return message if isinstance(message, str) else None
    return None


def execute_task(mission: Any, task_id: str, *, gate: Any, journal: Any,
                 now: Any = 0.0, session_id: str = "mission",
                 turn_index: int = 0,
                 decisions: Any = None,
                 tool_params: Any = None,
                 payloads: Any = None,
                 request_id: str = "") -> Tuple[Any, TaskReport]:
    """Exécute une tâche READY via les garde-fous existants (ou refuse)."""
    from core.loop.loop import request_confirmation, resolve_confirmation
    from core.p7.tools import prepare_call
    decisions = decisions if isinstance(decisions, dict) else {}
    tool_params = tool_params if isinstance(tool_params, dict) else {}
    payloads = payloads if isinstance(payloads, dict) else {}
    task = next((t for t in getattr(mission, "tasks", ())
                 if getattr(t, "id", "") == task_id), None)
    if task is None:
        return mission, TaskReport(task_id=str(task_id),
                                   demandee="inconnue",
                                   autorisation="absente",
                                   etat_final="refusee")
    demandee = str(getattr(task, "objective", ""))
    state = str(getattr(task, "state", ""))
    if state == "BLOCKED":
        capability = str(getattr(task, "required_capability", "") or "")
        ok, call = prepare_call(None, CAPABILITY_TO_TOOL.get(capability,
                                                             ""),
                                (tool_params if isinstance(tool_params,
                                                            dict) else {})
                                .get(task_id, {}),
                                request_id=(request_id or "mission-%s" % task_id))
        if not ok or CAPABILITY_TO_TOOL.get(capability) is None:
            return mission, TaskReport(
                task_id=task_id, demandee=demandee, autorisation="absente",
                etat_final="refusee",
                incertitude="tache-bloquee-non-rejouable")
        ok, mission = _set_task_state(mission, task_id, "READY")
        if not ok:
            return mission, TaskReport(
                task_id=task_id, demandee=demandee, autorisation="absente",
                etat_final="refusee", incertitude="reprise-impossible")
        task = next((t for t in getattr(mission, "tasks", ())
                     if getattr(t, "id", "") == task_id), task)
        state = "READY"
    if state != "READY":
        return mission, TaskReport(
            task_id=task_id, demandee=demandee, autorisation="absente",
            etat_final="refusee",
            incertitude="tache-non-prete:" + str(getattr(task, "state",
                                                          "")))
    ok, mission = _set_task_state(mission, task_id, "RUNNING")
    if not ok:
        return mission, TaskReport(
            task_id=task_id, demandee=demandee, autorisation="absente",
            etat_final="refusee", incertitude=str(mission))
    capability = str(getattr(task, "required_capability", "") or "")
    if not capability:
        ok, mission = _set_task_state(mission, task_id, "COMPLETED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee,
            autorisation="sans-objet-information", executee=False,
            resultat="informatif-sans-outil", verification="sans-objet",
            etat_final="terminee" if ok else "refusee")
    tool_id = CAPABILITY_TO_TOOL.get(capability)
    if tool_id is None:
        ok, mission = _set_task_state(mission, task_id, "BLOCKED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee, autorisation="absente",
            resultat="outil-indisponible:" + capability,
            verification="sans-objet",
            etat_final="bloquee" if ok else "refusee")
    ok, call = prepare_call(None, tool_id, tool_params.get(task_id, {}),
                            request_id=(request_id or "mission-%s" % task_id))
    if not ok:
        ok2, mission = _set_task_state(mission, task_id, "FAILED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee, autorisation="absente",
            resultat="preparation-impossible:" + str(call),
            verification="sans-objet",
            etat_final="echouee" if ok2 else "refusee")
    decision = decisions.get(task_id)
    if not isinstance(decision, (tuple, list)) or len(decision) < 2:
        ok2, mission = _set_task_state(mission, task_id, "BLOCKED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee,
            autorisation="en-attente-humaine",
            resultat="aucune-execution-sans-approbation",
            verification="sans-objet",
            etat_final="bloquee" if ok2 else "refusee")
    verdict, decided_by = str(decision[0]), decision[1]
    expires_at = decision[2] if len(decision) > 2 else None
    if verdict != "APPROVE":
        ok2, mission = _set_task_state(mission, task_id, "FAILED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee,
            autorisation="refusee-par:" + str(decided_by),
            resultat="aucune-execution", verification="sans-objet",
            etat_final="echouee" if ok2 else "refusee")
    ok_req, confirmation_id = request_confirmation(
        gate, call.request, session_id, turn_index, now,
        expires_at=expires_at)
    if not ok_req:
        _set_task_state(mission, task_id, "FAILED")
        ok2, mission = _set_task_state(mission, task_id, "FAILED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee,
            autorisation="approuve-par:" + str(decided_by),
            resultat="demande-impossible:" + str(confirmation_id),
            verification="sans-objet",
            etat_final="echouee" if ok2 else "refusee")
    resolved = resolve_confirmation(
        gate, confirmation_id, "APPROVE", decided_by,
        request=call.request, session_id=session_id,
        turn_index=turn_index, now=now, journal=journal,
        payload=_payload_for(call, payloads.get(task_id)))
    if getattr(resolved, "kind", "") != "CONFIRM_RESOLVED":
        ok2, mission = _set_task_state(mission, task_id, "FAILED")
        return mission, TaskReport(
            task_id=task_id, demandee=demandee,
            autorisation="approuve-par:" + str(decided_by),
            resultat="resolution:" + str(getattr(resolved, "detail", "")),
            verification=str(getattr(resolved, "verification",
                                     "sans-objet")),
            etat_final="echouee" if ok2 else "refusee")
    verification = str(getattr(resolved, "verification", "") or "")
    if verification == "VERIFIED_SUCCESS":
        ok2, mission = _set_task_state(mission, task_id, "COMPLETED")
        final = "terminee" if ok2 else "refusee"
    else:
        ok2, mission = _set_task_state(mission, task_id, "FAILED")
        final = "echouee" if ok2 else "refusee"
    return mission, TaskReport(
        task_id=task_id, demandee=demandee,
        autorisation="approuve-par:" + str(decided_by), executee=True,
        resultat=str(getattr(resolved, "detail", "")),
        verification=verification or "sans-objet",
        incertitude="" if verification == "VERIFIED_SUCCESS"
        else "verification-non-succes",
        etat_final=final)


def execute_mission(mission: Any, *, gate: Any, journal: Any,
                    now: Any = 0.0, session_id: str = "mission",
                    decisions: Any = None, tool_params: Any = None,
                    payloads: Any = None, request_id: str = "",
                    max_steps: int = 32) -> Tuple[Any, MissionReport]:
    """Avance une mission ACTIVE : prêtes → exécution → clôture ou pause."""
    reports: List[TaskReport] = []
    current = mission
    if getattr(current, "state", "") not in ("ACTIVE", "PAUSED"):
        return current, MissionReport(
            mission_id=str(getattr(current, "id", "")),
            etat_final=str(getattr(current, "state", "")),
            raison="mission-non-active")
    if getattr(current, "state", "") == "PAUSED":
        ok, current = _mission.transition_mission(current, "ACTIVE")
        if not ok:
            return current, MissionReport(
                mission_id=str(getattr(current, "id", "")),
                etat_final="PAUSED", raison="reprise-impossible")
    steps = 0
    while steps < max_steps:
        steps += 1
        current = _refresh(current)
        runnable = list(_mission.next_runnable(current)) + [
            task.id for task in getattr(current, "tasks", ())
            if getattr(task, "state", "") == "BLOCKED"]
        runnable = list(dict.fromkeys(runnable))
        if not runnable:
            break
        task_id = runnable[0]
        scoped = ("%s-%s" % (request_id, task_id)) if request_id else ""
        current, report = execute_task(
            current, task_id, gate=gate, journal=journal, now=now,
            session_id=session_id, turn_index=steps, decisions=decisions,
            tool_params=tool_params, payloads=payloads,
            request_id=scoped)
        reports.append(report)
        if report.etat_final != "terminee":
            break
    plan = tuple((t.id, t.state) for t in getattr(current, "tasks", ()))
    states = {state for _, state in plan}
    if states and states <= {"COMPLETED"}:
        ok, current = _mission.transition_mission(current, "COMPLETED")
        final = "COMPLETED" if ok else str(getattr(current, "state", ""))
        reason = "" if ok else "cloture-impossible"
    elif any(r.etat_final == "bloquee" for r in reports):
        ok, current = _mission.transition_mission(current, "PAUSED")
        final = "PAUSED" if ok else str(getattr(current, "state", ""))
        reason = "en-attente-approbation"
    else:
        final = str(getattr(current, "state", ""))
        reason = "taches-restantes" if states - {"COMPLETED"} else ""
    return current, MissionReport(
        mission_id=str(getattr(current, "id", "")),
        plan=plan, rapports=tuple(reports), etat_final=final,
        raison=reason)


def describe() -> Dict[str, Any]:
    """Contrat d'exécution (sans effet)."""
    return {"entree": "mission-ACTIVE", "outils": dict(CAPABILITY_TO_TOOL),
            "approbation": "humaine-explicite-injectee",
            "double-execution": "refusee",
            "network": False, "authority": False}
