"""Wilfrid — événements wake (P3.1). L'événement ne déclenche rien seul."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class WakeDetected:
    """Événement émis quand le mot d'éveil est confirmé (données seules)."""

    timestamp_monotonic: float
    probability: float
    phrase: str = "Wilfrid"
    frame_index: int = -1
    state: str = "TRIGGERED"
    diagnostics: Dict[str, Any] = field(default_factory=dict)


OnWakeCallback = Optional[object]  # typing: Callable[[WakeDetected], None]
