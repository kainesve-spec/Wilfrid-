"""Wilfrid — cycle de vie du runtime (P0-1, orchestration sans autorité).

États : INIT → CONFIGURED → READY → RUNNING → STOPPING → STOPPED.
Erreur : → ERROR → CLEANUP → STOPPED (jamais de faux READY).
Le runtime ORCHESTRE les composants validés (mémoire, knowledge, gate,
session, voix) ; il n'autorise rien et ne contourne aucune couche.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.runtime.config import RuntimeConfig, validate_config

STATES = ("INIT", "CONFIGURED", "READY", "RUNNING", "STOPPING", "STOPPED",
          "ERROR")

_TRANSITIONS = {
    "INIT": ("CONFIGURED", "ERROR"),
    "CONFIGURED": ("READY", "ERROR"),
    "READY": ("RUNNING", "STOPPING", "ERROR"),
    "RUNNING": ("STOPPING", "ERROR"),
    "STOPPING": ("STOPPED", "ERROR"),
    "ERROR": ("STOPPED",),
    "STOPPED": (),
}


@dataclass
class ComponentStatus:
    """État observable d'un composant (données seules)."""

    name: str = ""
    ready: bool = False
    detail: str = ""


@dataclass
class WilfridRuntime:
    """Runtime mince : init/arrêt déterministes, zéro autorité métier."""

    config: RuntimeConfig = field(default_factory=RuntimeConfig)
    state: str = "INIT"
    components: List[ComponentStatus] = field(default_factory=list)
    error: str = ""
    turn_count: int = 0
    _live: Any = field(default=None, repr=False)
    _gate: Any = field(default=None, repr=False)
    _memory: Any = field(default=None, repr=False)
    _kstore: Any = field(default=None, repr=False)
    _journal: Any = field(default=None, repr=False)
    _started: bool = field(default=False, repr=False)
    _missions: Any = field(default_factory=dict, repr=False)
    _mission_params: Any = field(default_factory=dict, repr=False)

    def _move(self, target: str, reason: str = "") -> Tuple[bool, str]:
        if target not in _TRANSITIONS.get(self.state, ()):  # pragma: no cover
            return False, "transition-invalide"
        self.state = target
        if reason:
            self.error = reason
        return True, "ok"

    def _mark(self, name: str, ready: bool, detail: str = "") -> None:
        self.components = [c for c in self.components if c.name != name]
        self.components.append(ComponentStatus(name=name, ready=ready,
                                               detail=detail))

    def start(self, *, now: float = 0.0) -> Tuple[bool, str]:
        """INIT → CONFIGURED → READY. Échec = ERROR + cleanup, jamais READY."""
        if self._started:
            return False, "double-initialisation"
        self._started = True
        ok, reason = validate_config(self.config)
        if not ok:
            self._move("ERROR", reason)
            self.cleanup()
            return False, reason
        resolved = self.config.resolved()
        if not self._move("CONFIGURED"):
            self._move("ERROR", "transition-invalide")
            self.cleanup()
            return False, "transition-invalide"
        try:
            from pathlib import Path as _Path
            for _p in (resolved.memory_path, resolved.knowledge_path,
                       resolved.journal_path):
                parent = _Path(_p).parent
                parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._move("ERROR", "donnees-inaccessibles")
            self.cleanup()
            return False, "donnees-inaccessibles"
        try:
            from core.memory.store import MemoryStore
            memory = MemoryStore(resolved.memory_path)
            self._memory = memory
            self._mark("memory", True, resolved.memory_path)
        except Exception:
            self._move("ERROR", "memoire-indisponible")
            self.cleanup()
            return False, "memoire-indisponible"
        try:
            from core.knowledge.store import KnowledgeStore
            kstore = KnowledgeStore(resolved.knowledge_path)
            self._kstore = kstore
        except Exception:
            self._move("ERROR", "knowledge-indisponible")
            self.cleanup()
            return False, "knowledge-indisponible"
        try:
            from core.knowledge.pack import ingest_pack
            ok, stats = ingest_pack(kstore, resolved.knowledge_pack_dir)
        except Exception:
            ok, stats = False, {"raison": "ingestion-impossible"}
        if ok:
            self._mark("knowledge", True,
                       "pack %d docs/%d chunks" % (
                           stats.get("documents", 0),
                           stats.get("chunks", 0)))
            self._mark("knowledge_pack", True, resolved.knowledge_pack_dir)
        else:
            self._mark("knowledge", False, str(stats.get("raison", "?")))
            self._mark("knowledge_pack", False,
                       str(stats.get("raison", "?")))
        try:
            from core.loop.live import open_session
            from core.p7.approval_gate import ApprovalGate
            from core.p7.journal import Journal
            from core.p7.resolver import ensure_jail
            journal = Journal(path=resolved.journal_path)
            self._journal = journal
            gate = ApprovalGate()
            self._gate = gate
            self._mark("p7", True, "gate+journal")
            ok, _, _ = ensure_jail()
            if not ok:
                raise RuntimeError("jail")
            self._mark("jail", True, "JAIL/P7")
            ok, live = open_session(resolved.session_id)
            if not ok:
                raise RuntimeError("session")
            self._live = live
            self._mark("session", True, resolved.session_id)
        except Exception:
            self._move("ERROR", "initialisation-p7-session")
            self.cleanup()
            return False, "initialisation-p7-session"
        try:
            from core.voice.stt_local import find_engine as find_stt
            from core.voice.tts_local import find_engine as find_tts
            _bin, _model, stt_ok, stt_why = find_stt()
            self._mark("stt", bool(stt_ok),
                       "" if stt_ok else str(stt_why))
            _m, _t, _d, tts_ok, tts_why = find_tts()
            self._mark("tts", bool(tts_ok),
                       "" if tts_ok else str(tts_why))
        except Exception:
            self._mark("stt", False, "sonde-impossible")
            self._mark("tts", False, "sonde-impossible")
        self._mark("core", True, "dialogue+router")
        if not self._move("READY")[0]:
            self._move("ERROR", "transition-invalide")
            self.cleanup()
            return False, "transition-invalide"
        return True, "ready"

    def status(self) -> Dict[str, Any]:
        """État observable (données seules)."""
        return {"state": self.state, "error": self.error,
                "turns": self.turn_count,
                "components": {c.name: {"ready": c.ready, "detail": c.detail}
                               for c in self.components}}

    def run_turn(self, text: Any, *, now: float = 0.0) -> Tuple[bool, Any]:
        """Un tour texte via la boucle existante. Runtime RUNNING requis."""
        if self.state != "RUNNING":
            return False, "etat-inattendu:" + self.state
        from core.cognitive.intent_router import route
        from core.cognitive.need_search import answer_search
        from core.loop.live import submit_turn

        def _search(output: Any) -> Any:
            if self._kstore is None:
                return None
            return answer_search(self._kstore, output, now=now)

        self._live, result = submit_turn(
            self._live, self._gate, text, now=now, source="text",
            search_fn=_search, router_fn=route, memory=self._memory,
            memorize=True, session_id=self._live.id)
        self.turn_count += 1
        return True, result

    def begin_running(self) -> Tuple[bool, str]:
        """READY → RUNNING (boucle interactive)."""
        if self.state != "READY":
            return False, "etat-inattendu:" + self.state
        ok, reason = self._move("RUNNING")
        return ok, reason

    def stop(self) -> Tuple[bool, str]:
        """STOPPING → cleanup → STOPPED. Idempotent après STOPPED."""
        if self.state == "STOPPED":
            return True, "deja-arrete"
        if self.state not in ("READY", "RUNNING", "STOPPING", "ERROR"):
            return False, "etat-inattendu:" + self.state
        self._move("STOPPING")
        self.cleanup()
        self._move("STOPPED")
        return True, "stopped"

    def cleanup(self) -> None:
        """Fermeture des ressources, sans exception."""
        for attr in ("_memory", "_kstore", "_journal"):
            handle = getattr(self, attr, None)
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._live = None
        self._gate = None
        try:
            self._missions = {}
            self._mission_params = {}
        except Exception:
            pass

    def submit_mission(self, spec: Any) -> Tuple[bool, str]:
        """Enregistre une mission explicite (aucune exécution)."""
        if self.state not in ("READY", "RUNNING"):
            return False, "etat-inattendu:" + self.state
        if not isinstance(spec, dict):
            return False, "spec-invalide"
        try:
            from core.mission.mission import create_mission
            ok, mission = create_mission(
                mission_id=spec.get("id", ""),
                objective=spec.get("objective", ""),
                context=str(spec.get("context", "")),
                tasks=spec.get("tasks", ()),
                allowed_capabilities=spec.get("allowed_capabilities", ()),
                provenance="operateur")
        except Exception:
            return False, "creation-impossible"
        if not ok:
            return False, str(mission)[:80]
        self._missions[mission.id] = mission
        try:
            params = {}
            for spec in spec.get("tasks", ()):
                if isinstance(spec, dict) and isinstance(
                        spec.get("id"), str):
                    task_params = spec.get("params", {})
                    if isinstance(task_params, dict):
                        params[spec["id"]] = {
                            str(k): v for k, v in task_params.items()}
            self._mission_params[mission.id] = params
        except Exception:
            pass
        return True, mission.id

    def list_missions(self) -> List[Tuple[str, str]]:
        """Inventaire (id, état), ordre stable."""
        try:
            items = list(self._missions.items())
        except Exception:
            return []
        return sorted((mid, getattr(m, "state", "?")) for mid, m in items)

    def get_mission(self, mission_id: Any) -> Any:
        """Mission par id exact, `None` si inconnue."""
        try:
            return self._missions.get(mission_id) \
                if isinstance(mission_id, str) else None
        except Exception:
            return None

    def run_mission(self, mission_id: Any, *,
                    decisions: Any = None,
                    tool_params: Any = None,
                    now: Any = 0.0) -> Tuple[bool, Any]:
        """Avance une mission (décisions humaines explicites uniquement)."""
        if self.state not in ("READY", "RUNNING"):
            return False, "etat-inattendu:" + self.state
        mission = self.get_mission(mission_id)
        if mission is None:
            return False, "mission-introuvable"
        try:
            from core.mission.execution import execute_mission
            from core.mission.mission import transition_mission
            if getattr(mission, "state", "") == "CREATED":
                ok, mission = transition_mission(mission, "ACTIVE")
                if not ok:
                    return False, str(mission)[:80]
                self._missions[mission.id] = mission
            updated, report = execute_mission(
                mission, gate=self._gate, journal=self._journal, now=now,
                session_id=self.config.session_id,
                decisions=decisions if isinstance(decisions, dict) else {},
                tool_params=dict(
                    self._mission_params.get(mission.id, {})),
                request_id="run-%s" % mission.id)
            self._missions[updated.id] = updated
            return True, report
        except Exception:
            return False, "execution-impossible"


def create_runtime(config: Any = None, *,
                   now: float = 0.0) -> Tuple[bool, WilfridRuntime]:
    """Fabrique + démarre jusqu'à READY (ou ERROR propre)."""
    runtime = WilfridRuntime(
        config=config if isinstance(config, RuntimeConfig)
        else RuntimeConfig())
    ok, reason = runtime.start(now=now)
    logging.getLogger("wilfrid.runtime").info("runtime=%s %s",
                                              runtime.state, reason)
    return ok, runtime
