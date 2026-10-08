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
    _journal: Any = field(default=None, repr=False)
    _started: bool = field(default=False, repr=False)

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
            store = KnowledgeStore(resolved.knowledge_path)
            store.close()
            self._mark("knowledge", True, resolved.knowledge_path)
        except Exception:
            self._move("ERROR", "knowledge-indisponible")
            self.cleanup()
            return False, "knowledge-indisponible"
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
        from core.loop.live import submit_turn
        self._live, result = submit_turn(
            self._live, self._gate, text, now=now, source="text",
            memory=self._memory, memorize=True,
            session_id=self._live.id)
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
        for attr in ("_memory", "_journal"):
            handle = getattr(self, attr, None)
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._live = None
        self._gate = None


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
