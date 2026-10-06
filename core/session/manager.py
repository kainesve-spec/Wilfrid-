"""Wilfrid — Session Manager (P4). Unique consommateur de WAKE_DETECTED.

Transitions : IDLE --(WAKE_DETECTED)--> ACTIVATING --> ACTIVE -->
LISTENING <-> WAITING --> IDLE ; ENDED / ERROR terminaux.
PROCESSING / RESPONDING : stubs documentés, jamais atteints en P4.

Bornes : une seule session active ; double wake = refresh du timeout,
jamais de seconde session ; journal JSONL OFF par défaut (événements
techniques seuls, 64 Ko, 1 rotation) ; salut quotidien = une date
dans `.cache/last_greeting`, rien d'autre. Aucune autorité d'action :
pas de subprocess/socket/webbrowser/SQLite/réseau ici.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.session import events as _events
from core.session.context import SessionContext
from core.session.identity import WilfridIdentity
from core.session.session import (
    DEFAULT_INACTIVITY_TIMEOUT_S,
    Session,
    new_session_id,
)
from core.session.state import SessionState
from core.wake.events import WakeDetected

log = logging.getLogger("wilfrid.session")

JOURNAL_MAX_BYTES = 64 * 1024

_JOURNAL_FIELDS = ("session_id", "timestamp_monotonic", "cause",
                   "counters", "state", "event")


class SessionJournal:
    """Journal diagnostique JSONL, OFF par défaut. Événements techniques seuls."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else None
        self.enabled = path is not None

    def write(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.enabled or self.path is None:
            return
        safe = {k: payload.get(k) for k in _JOURNAL_FIELDS if k in payload}
        line = json.dumps({"event": event_type, **safe},
                          ensure_ascii=False) + "\n"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = line.encode("utf-8")
            if self.path.is_file() and (
                    self.path.stat().st_size + len(data) > JOURNAL_MAX_BYTES):
                rotated = self.path.with_suffix(self.path.suffix + ".1")
                try:
                    if rotated.is_file():
                        rotated.unlink()
                except OSError:
                    pass
                try:
                    self.path.rename(rotated)
                except OSError:
                    return
            with open(self.path, "ab") as fh:
                fh.write(data)
        except OSError:
            pass  # best-effort : le journal ne casse jamais la session


def _today_iso() -> str:
    return datetime.date.today().isoformat()


def greeting_done_today(path: Optional[Path],
                        today: Optional[str] = None) -> bool:
    """Le salut quotidien a-t-il déjà été effectué ? Une date, rien d'autre."""
    if path is None:
        return False
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return content == (today or _today_iso())


def mark_greeting_done(path: Optional[Path],
                       today: Optional[str] = None) -> None:
    """Enregistre la date du jour uniquement (aucune autre donnée)."""
    if path is None:
        return
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((today or _today_iso()) + "\n", encoding="utf-8")
    except OSError:
        pass


class SessionManager:
    """Orchestre une session locale. Aucune action externe possible."""

    def __init__(self, identity: Optional[WilfridIdentity] = None,
                 inactivity_timeout_s: float = DEFAULT_INACTIVITY_TIMEOUT_S,
                 greeting_path: Optional[Path] = None,
                 journal_path: Optional[Path] = None,
                 now: Optional[Callable[[], float]] = None):
        self.identity = identity or WilfridIdentity()
        self.inactivity_timeout_s = inactivity_timeout_s
        self.greeting_path = Path(greeting_path) if greeting_path else None
        self.journal = SessionJournal(journal_path)
        self._now = now or time.monotonic
        self.session: Optional[Session] = None
        self.events: List[Any] = []

    # ------------------------------------------------------------- internes
    def _emit(self, event: Any) -> None:
        self.events.append(event)
        state = getattr(getattr(self.session, "state", None), "value", "")
        self.journal.write(type(event).__name__, {
            "session_id": getattr(event, "session_id", ""),
            "timestamp_monotonic": getattr(event, "timestamp_monotonic", 0.0),
            "cause": getattr(event, "cause", ""),
            "counters": dict(getattr(event, "counters", {}) or {}),
            "state": state,
            "event": type(event).__name__,
        })

    def _new_session(self, now: float, cause: str) -> Session:
        session = Session(
            session_id=new_session_id(),
            state=SessionState.ACTIVATING,
            created_monotonic=now,
            last_activity_monotonic=now,
            inactivity_timeout_s=self.inactivity_timeout_s,
        )
        self.session = session
        self._emit(_events.SessionStarted(
            session_id=session.session_id,
            timestamp_monotonic=now, cause=cause, counters={}))
        return session

    # -------------------------------------------------------------- entrées
    def on_wake(self, event: WakeDetected,
                now: Optional[float] = None) -> Optional[Session]:
        """IDLE --(WAKE_DETECTED)--> ACTIVATING-->ACTIVE ; sinon refresh."""
        moment = self._now() if now is None else now
        current = self.session
        if current is None or current.state in (SessionState.IDLE,
                                                SessionState.ENDED,
                                                SessionState.ERROR):
            session = self._new_session(moment, cause="wake")
            session.state = SessionState.ACTIVE
            self._emit(_events.ListeningStarted(
                session_id=session.session_id,
                timestamp_monotonic=moment, cause="active", counters={}))
            return session
        current.touch(moment)  # double wake : refresh uniquement
        return current

    def check_timeout(self, now: Optional[float] = None) -> Optional[Session]:
        """Ferme la session inactive au-delà du timeout (60 s, paramétrable)."""
        moment = self._now() if now is None else now
        current = self.session
        if current is None or current.state in (SessionState.ENDED,
                                                SessionState.ERROR,
                                                SessionState.IDLE):
            return current
        if current.expired(moment):
            return self.close("timeout", now=moment)
        return current

    def close(self, cause: str = "close",
              now: Optional[float] = None) -> Optional[Session]:
        """Fermeture explicite + purge complète du contexte."""
        moment = self._now() if now is None else now
        current = self.session
        if current is None:
            return None
        current.context.purge()
        current.state = SessionState.ENDED
        self._emit(_events.SessionEnded(
            session_id=current.session_id,
            timestamp_monotonic=moment, cause=cause, counters={}))
        return current

    def fail(self, cause: str = "error", detail: Optional[str] = None,
             now: Optional[float] = None) -> Optional[Session]:
        moment = self._now() if now is None else now
        current = self.session
        if current is None:
            return None
        current.state = SessionState.ERROR
        self._emit(_events.SessionError(
            session_id=current.session_id,
            timestamp_monotonic=moment, cause=cause,
            counters={}, detail=detail))
        return current

    def stop_listening(self, cause: str = "timeout",
                       now: Optional[float] = None) -> Optional[Session]:
        moment = self._now() if now is None else now
        current = self.session
        if current is None:
            return None
        self._emit(_events.ListeningStopped(
            session_id=current.session_id,
            timestamp_monotonic=moment, cause=cause, counters={}))
        return current

    # ------------------------------------------------------- activation
    def activation_response(self) -> str:
        """Texte d'accusé (donnée, aucun TTS câblé en P4)."""
        return self.identity.activation_response()

    def should_greet_today(self, today: Optional[str] = None) -> bool:
        """True si le salut quotidien reste à effectuer (une date suffit)."""
        return not greeting_done_today(self.greeting_path, today=today)

    def mark_greeted(self, today: Optional[str] = None) -> None:
        mark_greeting_done(self.greeting_path, today=today)
