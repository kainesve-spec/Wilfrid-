"""Wilfrid — détecteur à états (P3.1). Logique pure, sans I/O ni modèle.

Sémantique validée au diagnostic (cf. heed/infer.py) :
- seuil appliqué à la probabilité BRUTE (EMA = observabilité seule) ;
- `consecutive_frames` probabilités > seuil d'affilée → candidat ;
- refractory après chaque trigger ; reset du candidat sur gate fermée,
  prob sous seuil, arrêt ou erreur fatale.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.wake.events import WakeDetected


class DetectorState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    GATED = "GATED"
    CANDIDATE = "CANDIDATE"
    TRIGGERED = "TRIGGERED"
    REFRACTORY = "REFRACTORY"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class WakeRuntimeConfig:
    """Configuration lue depuis models/wake.json (jamais codée en dur)."""

    threshold: float
    consecutive_frames: int
    refractory_seconds: float
    ema_alpha: float
    energy_dbfs: float
    voice_band_min: float
    band_lo_hz: float
    band_hi_hz: float
    sample_rate: int
    phrase: str = "Wilfrid"

    @classmethod
    def from_wake_json(cls, path: str | Path) -> "WakeRuntimeConfig":
        with open(path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        trigger = meta.get("trigger", {})
        gate = meta.get("energy_gate", {})
        return cls(
            threshold=float(meta["threshold"]),
            consecutive_frames=int(trigger.get("consecutive_frames", 2)),
            refractory_seconds=float(trigger.get("refractory_seconds", 0.7)),
            ema_alpha=float(trigger.get("ema_alpha", 0.5)),
            energy_dbfs=float(gate.get("rms_threshold_dbfs", -55.0)),
            voice_band_min=float(gate.get("voice_band_min_fraction", 0.15)),
            band_lo_hz=float(gate.get("voice_band_lo_hz", 100.0)),
            band_hi_hz=float(gate.get("voice_band_hi_hz", 7000.0)),
            sample_rate=int(meta.get("sample_rate", 16000)),
            phrase=str(meta.get("phrase", "Wilfrid")),
        )


class WakeDetector:
    """Machine à états du trigger. `step(prob, gate_open, now)` pur."""

    def __init__(self, config: WakeRuntimeConfig,
                 on_wake: Optional[Callable[[WakeDetected], None]] = None):
        self.config = config
        self.on_wake = on_wake
        self.state = DetectorState.IDLE
        self.ema = 0.0
        self.above = 0
        self.last_trigger_time = -1e9
        self.last_probability = 0.0
        self.last_event_timestamp: Optional[float] = None
        self.metrics: Dict[str, Any] = {
            "windows_scored": 0,
            "gate_open": 0,
            "gate_closed": 0,
            "scores_above_threshold": 0,
            "triggers": 0,
        }
        self.events: List[WakeDetected] = []

    def start(self) -> None:
        self.state = DetectorState.LISTENING

    def stop(self) -> None:
        self.state = DetectorState.STOPPED
        self.above = 0

    def fail(self, reason: str) -> None:
        self.state = DetectorState.ERROR
        self.above = 0
        self.metrics["error"] = reason

    def step(self, prob: float, gate_open: bool,
             now: Optional[float] = None,
             frame_index: int = -1) -> Optional[WakeDetected]:
        """Avance d'une fenêtre. Retourne l'événement s'il y a trigger."""
        if now is None:
            now = time.monotonic()
        if self.state in (DetectorState.STOPPED, DetectorState.ERROR):
            return None
        self.metrics["windows_scored"] += 1
        self.last_probability = prob
        self.ema = self.config.ema_alpha * prob + (1.0 - self.config.ema_alpha) * self.ema
        if not gate_open:
            self.metrics["gate_closed"] += 1
            self.above = 0
            if self.state not in (DetectorState.REFRACTORY,):
                self.state = DetectorState.GATED
            return None
        self.metrics["gate_open"] += 1
        if self.state == DetectorState.REFRACTORY:
            if now - self.last_trigger_time <= self.config.refractory_seconds:
                return None
            self.state = DetectorState.LISTENING
        if prob > self.config.threshold:
            self.metrics["scores_above_threshold"] += 1
            self.above += 1
            self.state = DetectorState.CANDIDATE
        else:
            self.above = 0
            if self.state == DetectorState.CANDIDATE:
                self.state = DetectorState.LISTENING
            elif self.state == DetectorState.GATED:
                self.state = DetectorState.LISTENING
            return None
        if self.above >= self.config.consecutive_frames and (
                now - self.last_trigger_time) > self.config.refractory_seconds:
            self.last_trigger_time = now
            self.above = 0
            self.state = DetectorState.TRIGGERED
            event = WakeDetected(
                timestamp_monotonic=now,
                probability=prob,
                phrase=self.config.phrase,
                frame_index=frame_index,
                diagnostics={"ema": self.ema},
            )
            self.metrics["triggers"] += 1
            self.last_event_timestamp = now
            self.events.append(event)
            if self.on_wake is not None:
                self.on_wake(event)
            self.state = DetectorState.REFRACTORY
            return event
        return None
