"""Wilfrid — événements minimaux de session (P4). Données pures.

WAKE_DETECTED est réutilisé depuis core.wake.events (jamais redéfini).
Sont exclus tant qu'aucun moteur ne les justifie : SESSION_ACTIVE,
PROCESSING_*, RESPONSE_*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SessionStarted:
    session_id: str
    timestamp_monotonic: float
    cause: str = "wake"
    counters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionEnded:
    session_id: str
    timestamp_monotonic: float
    cause: str = "close"
    counters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ListeningStarted:
    session_id: str
    timestamp_monotonic: float
    cause: str = "active"
    counters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ListeningStopped:
    session_id: str
    timestamp_monotonic: float
    cause: str = "timeout"
    counters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionError:
    session_id: str
    timestamp_monotonic: float
    cause: str = "error"
    counters: Dict[str, Any] = field(default_factory=dict)
    detail: Optional[str] = None
