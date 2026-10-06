"""Wilfrid — états d'interaction (P4). PROCESSING/RESPONDING = stubs."""

from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"  # stub P4 : aucun moteur
    RESPONDING = "RESPONDING"  # stub P4 : aucun moteur
    WAITING = "WAITING"
    ENDED = "ENDED"
    ERROR = "ERROR"
