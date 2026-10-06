"""Wilfrid — session locale (P4). Une seule session active par manager."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from core.session.context import SessionContext
from core.session.state import SessionState

DEFAULT_INACTIVITY_TIMEOUT_S = 60.0


@dataclass
class Session:
    """Session d'interaction : état + contexte volatile + échéances."""

    session_id: str = ""
    state: SessionState = SessionState.IDLE
    created_monotonic: float = 0.0
    last_activity_monotonic: float = 0.0
    inactivity_timeout_s: float = DEFAULT_INACTIVITY_TIMEOUT_S
    context: SessionContext = field(default_factory=SessionContext)

    def touch(self, now: float) -> None:
        self.last_activity_monotonic = now

    def expired(self, now: float) -> bool:
        return (now - self.last_activity_monotonic) > self.inactivity_timeout_s


def new_session_id() -> str:
    return uuid.uuid4().hex


def now_monotonic() -> float:
    return time.monotonic()
