"""Wilfrid — missions et orchestration gouvernée (Master 5).

Modèle d'états pur, sans exécution : l'orchestrateur décide de l'ordre et de
l'état des tâches, jamais d'effet. Une mission ne crée aucune permission et
ne peut pas augmenter l'autorité : toute tâche exigeant une capacité hors
mandat est BLOQUÉE avec motif explicite, et les actions sensibles restent
soumises aux contrôles existants (P7/gouverneur) hors de ce module.

Règles : transitions explicites et vérifiées (aucune implicite) ; échecs
explicites ; reprise/replanification bornée ; arrêt explicite ; parallélisme
uniquement déclaré sûr ; déterminisme total (tris stables, aucun hash/temps/
aléatoire) ; hostile = donnée inerte (résolution exacte par identifiant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MISSION_STATES = ("CREATED", "ACTIVE", "PAUSED", "FAILED", "COMPLETED",
                  "CANCELLED")
TASK_STATES = ("PENDING", "READY", "RUNNING", "BLOCKED", "FAILED",
               "COMPLETED")

_MISSION_TRANSITIONS = {
    "CREATED": ("ACTIVE", "CANCELLED"),
    "ACTIVE": ("PAUSED", "FAILED", "COMPLETED", "CANCELLED"),
    "PAUSED": ("ACTIVE", "FAILED", "CANCELLED"),
    "FAILED": (),
    "COMPLETED": (),
    "CANCELLED": (),
}

_TASK_TRANSITIONS = {
    "PENDING": ("READY", "BLOCKED", "FAILED"),
    "READY": ("RUNNING", "BLOCKED", "FAILED"),
    "RUNNING": ("COMPLETED", "FAILED", "BLOCKED"),
    "BLOCKED": ("READY", "FAILED"),
    "FAILED": ("READY",),
    "COMPLETED": (),
}

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_REPLANS = 3


@dataclass(frozen=True)
class Task:
    """Étape : objectif, dépendances exactes, état, capacité éventuelle."""

    id: str = ""
    objective: str = ""
    dependencies: Tuple[str, ...] = ()
    state: str = "PENDING"
    priority: int = 0
    required_capability: str = ""
    parallel_safe: bool = False
    attempts: int = 0
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    result: str = ""
    reason: str = ""


@dataclass(frozen=True)
class Mission:
    """Mission : objectif, tâches, contraintes, provenance, état."""

    id: str = ""
    objective: str = ""
    context: str = ""
    state: str = "CREATED"
    priority: int = 0
    tasks: Tuple[Task, ...] = ()
    allowed_capabilities: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    provenance: str = ""
    replans: int = 0
    max_replans: int = DEFAULT_MAX_REPLANS


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


def _has_cycle(tasks: Dict[str, Task]) -> bool:
    visiting: List[str] = []
    done = set()

    def visit(task_id: str) -> bool:
        if task_id in done:
            return False
        if task_id in visiting:
            return True
        visiting.append(task_id)
        task = tasks.get(task_id)
        if task is not None:
            for dep in task.dependencies:
                if dep in tasks and visit(dep):
                    return True
        visiting.pop()
        done.add(task_id)
        return False

    return any(visit(task_id) for task_id in sorted(tasks))


def create_mission(mission_id: Any, objective: Any, *,
                   context: str = "", priority: int = 0,
                   tasks: Any = (),
                   allowed_capabilities: Any = (),
                   constraints: Any = (),
                   provenance: str = "",
                   max_replans: int = DEFAULT_MAX_REPLANS) -> Tuple[bool, Any]:
    """Crée une mission CREATED. Refus contrôlés, jamais d'exception métier."""
    if not _valid_id(mission_id) or not isinstance(objective, str) \
            or not objective.strip() or len(objective) > 2000:
        return False, "mission-invalide"
    if not isinstance(priority, int) or isinstance(priority, bool):
        return False, "mission-invalide"
    if not isinstance(tasks, (tuple, list)) or not tasks:
        return False, "sans-taches"
    if not isinstance(max_replans, int) or isinstance(max_replans, bool) \
            or not 0 <= max_replans <= 10:
        return False, "mission-invalide"
    allowed = tuple(c for c in (allowed_capabilities or ())
                    if isinstance(c, str) and c.strip())
    built: Dict[str, Task] = {}
    for index, spec in enumerate(tasks):
        if not isinstance(spec, dict):
            return False, f"tache-invalide:{index}"
        task_id = spec.get("id", "")
        if not _valid_id(task_id) or task_id in built:
            return False, f"tache-invalide:{index}"
        deps = spec.get("dependencies", ())
        if not isinstance(deps, (tuple, list)) or any(
                not isinstance(d, str) for d in deps):
            return False, f"tache-invalide:{index}"
        if task_id in deps:
            return False, f"dependance-cyclique:{task_id}"
        capability = spec.get("required_capability", "")
        if capability and capability not in allowed:
            built[task_id] = Task(
                id=task_id,
                objective=str(spec.get("objective", ""))[:2000],
                dependencies=tuple(deps), state="BLOCKED", priority=0,
                required_capability=str(capability),
                reason="capability-not-allowed")
            continue
        parallel = spec.get("parallel_safe", False)
        built[task_id] = Task(
            id=task_id, objective=str(spec.get("objective", ""))[:2000],
            dependencies=tuple(deps), state="PENDING",
            priority=spec.get("priority", 0)
            if isinstance(spec.get("priority", 0), int)
            and not isinstance(spec.get("priority", 0), bool) else 0,
            required_capability=str(capability),
            parallel_safe=bool(parallel),
            max_attempts=spec.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
            if isinstance(spec.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
                           int) and not isinstance(
                spec.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
                bool) and 1 <= spec.get("max_attempts",
                                        DEFAULT_MAX_ATTEMPTS) <= 10
            else DEFAULT_MAX_ATTEMPTS)
    for task_id, task in built.items():
        for dep in task.dependencies:
            if dep not in built:
                return False, f"dependance-inconnue:{dep}"
    if _has_cycle(built):
        return False, "dependance-cyclique"
    ordered = tuple(built[task_id] for task_id in sorted(built))
    mission = Mission(
        id=str(mission_id), objective=str(objective).strip(),
        context=str(context or "")[:2000],
        state="CREATED", priority=priority, tasks=ordered,
        allowed_capabilities=tuple(sorted(set(allowed))),
        constraints=tuple(str(c)[:256] for c in (constraints or [])
                          if isinstance(c, str)),
        provenance=str(provenance or "")[:256], replans=0,
        max_replans=max_replans)
    return True, mission


def _replace_task(mission: Mission, task: Task) -> Mission:
    tasks = tuple(task if current.id == task.id else current
                  for current in mission.tasks)
    return Mission(id=mission.id, objective=mission.objective,
                   context=mission.context, state=mission.state,
                   priority=mission.priority, tasks=tasks,
                   allowed_capabilities=mission.allowed_capabilities,
                   constraints=mission.constraints,
                   provenance=mission.provenance, replans=mission.replans,
                   max_replans=mission.max_replans)


def transition_mission(mission: Mission,
                       target: str) -> Tuple[bool, Any]:
    """Transition explicite de mission. Terminaux figés, sans effet."""
    if not isinstance(mission, Mission) or target not in _MISSION_TRANSITIONS.get(
            mission.state, ()):
        return False, "transition-invalide"
    if target == "COMPLETED":
        pending = [task.id for task in mission.tasks
                   if task.state != "COMPLETED"]
        if pending:
            return False, "taches-inachevees"
    updated = Mission(id=mission.id, objective=mission.objective,
                      context=mission.context, state=target,
                      priority=mission.priority, tasks=mission.tasks,
                      allowed_capabilities=mission.allowed_capabilities,
                      constraints=mission.constraints,
                      provenance=mission.provenance,
                      replans=mission.replans,
                      max_replans=mission.max_replans)
    return True, updated


def transition_task(mission: Mission, task_id: str,
                    target: str) -> Tuple[bool, Any]:
    """Transition explicite de tâche, bornes d'essais respectées."""
    current = next((task for task in mission.tasks if task.id == task_id),
                   None)
    if current is None or target not in _TASK_TRANSITIONS.get(
            current.state, ()):
        return False, "transition-invalide"
    if mission.state not in ("ACTIVE", "PAUSED"):
        return False, "mission-non-active"
    attempts = current.attempts
    if target == "RUNNING":
        if attempts >= current.max_attempts:
            return False, "essais-epuises"
        attempts += 1
    updated_task = Task(
        id=current.id, objective=current.objective,
        dependencies=current.dependencies, state=target,
        priority=current.priority,
        required_capability=current.required_capability,
        parallel_safe=current.parallel_safe, attempts=attempts,
        max_attempts=current.max_attempts, result=current.result,
        reason=current.reason)
    return True, _replace_task(mission, updated_task)


def refresh_ready(mission: Mission) -> Mission:
    """PENDING → READY quand toutes les dépendances sont COMPLETED. Pur."""
    states = {task.id: task.state for task in mission.tasks}
    updated = []
    for task in mission.tasks:
        if task.state == "PENDING" and all(
                states.get(dep) == "COMPLETED" for dep in task.dependencies):
            updated.append(Task(
                id=task.id, objective=task.objective,
                dependencies=task.dependencies, state="READY",
                priority=task.priority,
                required_capability=task.required_capability,
                parallel_safe=task.parallel_safe, attempts=task.attempts,
                max_attempts=task.max_attempts, result=task.result,
                reason=task.reason))
        else:
            updated.append(task)
    return Mission(id=mission.id, objective=mission.objective,
                   context=mission.context, state=mission.state,
                   priority=mission.priority, tasks=tuple(updated),
                   allowed_capabilities=mission.allowed_capabilities,
                   constraints=mission.constraints,
                   provenance=mission.provenance, replans=mission.replans,
                   max_replans=mission.max_replans)


def propagate_blocks(mission: Mission) -> Mission:
    """Dépendances d'une tâche FAILED → BLOCKED (motif explicite). Pur."""
    failed = {task.id for task in mission.tasks if task.state == "FAILED"}
    if not failed:
        return mission
    updated = []
    for task in mission.tasks:
        if task.state in ("PENDING", "READY") and any(
                dep in failed for dep in task.dependencies):
            updated.append(Task(
                id=task.id, objective=task.objective,
                dependencies=task.dependencies, state="BLOCKED",
                priority=task.priority,
                required_capability=task.required_capability,
                parallel_safe=task.parallel_safe, attempts=task.attempts,
                max_attempts=task.max_attempts, result=task.result,
                reason="dependance-en-echec"))
        else:
            updated.append(task)
    return Mission(id=mission.id, objective=mission.objective,
                   context=mission.context, state=mission.state,
                   priority=mission.priority, tasks=tuple(updated),
                   allowed_capabilities=mission.allowed_capabilities,
                   constraints=mission.constraints,
                   provenance=mission.provenance, replans=mission.replans,
                   max_replans=mission.max_replans)


def replan(mission: Mission) -> Tuple[bool, Any]:
    """Replanification bornée : BLOCKED/FAILED → PENDING, compteur incrémenté."""
    if mission.replans >= mission.max_replans:
        return False, "replanifications-epuisees"
    updated = []
    for task in mission.tasks:
        if task.state in ("BLOCKED", "FAILED"):
            updated.append(Task(
                id=task.id, objective=task.objective,
                dependencies=task.dependencies, state="PENDING",
                priority=task.priority,
                required_capability=task.required_capability,
                parallel_safe=task.parallel_safe, attempts=task.attempts,
                max_attempts=task.max_attempts, result=task.result,
                reason="replanifie"))
        else:
            updated.append(task)
    return True, Mission(
        id=mission.id, objective=mission.objective, context=mission.context,
        state=mission.state, priority=mission.priority,
        tasks=tuple(updated),
        allowed_capabilities=mission.allowed_capabilities,
        constraints=mission.constraints, provenance=mission.provenance,
        replans=mission.replans + 1, max_replans=mission.max_replans)


def next_runnable(mission: Mission) -> List[str]:
    """Tâches READY ordonnées : priorité décroissante, id croissant."""
    ready = [task for task in mission.tasks if task.state == "READY"]
    ready.sort(key=lambda task: (-task.priority, task.id))
    return [task.id for task in ready]


def can_parallel(left: Task, right: Task) -> bool:
    """Parallélisme sûr : déclaré des deux côtés + indépendance mutuelle."""
    if not isinstance(left, Task) or not isinstance(right, Task):
        return False
    if left.id == right.id:
        return False
    return bool(left.parallel_safe and right.parallel_safe
                and left.id not in right.dependencies
                and right.id not in left.dependencies)


def snapshot(mission: Mission) -> Dict[str, Any]:
    """État opérationnel sérialisable (persistance explicite par l'appelant)."""
    return {
        "id": mission.id, "objective": mission.objective,
        "context": mission.context, "state": mission.state,
        "priority": mission.priority,
        "tasks": [{"id": task.id, "objective": task.objective,
                   "dependencies": list(task.dependencies),
                   "state": task.state, "priority": task.priority,
                   "required_capability": task.required_capability,
                   "parallel_safe": task.parallel_safe,
                   "attempts": task.attempts,
                   "max_attempts": task.max_attempts, "result": task.result,
                   "reason": task.reason} for task in mission.tasks],
        "allowed_capabilities": list(mission.allowed_capabilities),
        "constraints": list(mission.constraints),
        "provenance": mission.provenance, "replans": mission.replans,
        "max_replans": mission.max_replans,
    }


def describe(mission: Mission) -> Dict[str, Any]:
    """Résumé borné sans contenu sensible supposé (objectifs déjà fournis)."""
    counts: Dict[str, int] = {}
    for task in mission.tasks:
        counts[task.state] = counts.get(task.state, 0) + 1
    return {"id": mission.id, "state": mission.state,
            "tasks": len(mission.tasks), "by_state": counts,
            "replans": mission.replans}
