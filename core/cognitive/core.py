"""Wilfrid — Cognitive Core P5 (orchestration sans effets).

IDLE → INPUT_RECEIVED → ANALYZING → DECIDING → PLANNING → READY
(+ CLARIFICATION_REQUIRED, ERROR). READY = décision produite, jamais
d'action exécutée. Transitions explicites, pas de récursion, borné.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.cognitive import classifier as _classifier
from core.cognitive import decider as _decider
from core.cognitive import planner as _planner
from core.cognitive.input import CognitiveInputError, build_input
from core.cognitive.types import CognitiveOutput, IntentKind


class CognitiveState(str, Enum):
    IDLE = "IDLE"
    INPUT_RECEIVED = "INPUT_RECEIVED"
    ANALYZING = "ANALYZING"
    DECIDING = "DECIDING"
    PLANNING = "PLANNING"
    READY = "READY"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    ERROR = "ERROR"


_TRANSITIONS = {
    CognitiveState.IDLE: (CognitiveState.INPUT_RECEIVED, CognitiveState.ERROR),
    CognitiveState.INPUT_RECEIVED: (CognitiveState.ANALYZING, CognitiveState.ERROR),
    CognitiveState.ANALYZING: (CognitiveState.DECIDING, CognitiveState.ERROR),
    CognitiveState.DECIDING: (CognitiveState.PLANNING,
                              CognitiveState.CLARIFICATION_REQUIRED,
                              CognitiveState.ERROR),
    CognitiveState.PLANNING: (CognitiveState.READY,
                              CognitiveState.CLARIFICATION_REQUIRED,
                              CognitiveState.ERROR),
    CognitiveState.READY: (CognitiveState.IDLE,),
    CognitiveState.CLARIFICATION_REQUIRED: (CognitiveState.IDLE,),
    CognitiveState.ERROR: (CognitiveState.IDLE,),
}


@dataclass
class CognitiveResult:
    """Sortie du core : décision + plan abstrait + trace d'états."""

    output: CognitiveOutput
    plan: List[Dict[str, str]]
    states: List[str]
    state: CognitiveState


class CognitiveCore:
    """Moteur borné, déterministe, sans I/O ni effets externes."""

    def __init__(self, on_result: Optional[
            Callable[[CognitiveResult], None]] = None):
        self.on_result = on_result
        self.state = CognitiveState.IDLE
        self._trace: List[str] = []
        self.metrics: Dict[str, Any] = {
            "processed": 0,
            "errors": 0,
            "clarifications": 0,
            "refusals": 0,
        }

    def _go(self, target: CognitiveState) -> None:
        allowed = _TRANSITIONS.get(self.state, ())
        if target not in allowed:
            raise ValueError(f"transition {self.state} -> {target} interdite")
        self.state = target
        self._trace.append(target.value)

    def reset(self) -> None:
        self.state = CognitiveState.IDLE
        self._trace = []

    def process(self, text: str, session_id: str,
                context_snapshot: List[Dict[str, Any]], timestamp: float,
                source: str,
                stt_confidence: Optional[float] = None) -> CognitiveResult:
        """Pipeline complet : validation → classification → décision → plan."""
        self.reset()
        try:
            cognitive_input = build_input(
                text, session_id, context_snapshot, timestamp, source,
                stt_confidence)
            self._go(CognitiveState.INPUT_RECEIVED)
            classification = _classifier.classify(cognitive_input.text)
            self._go(CognitiveState.ANALYZING)
            decision = _decider.decide(classification, cognitive_input)
            self._go(CognitiveState.DECIDING)
            plan = _planner.build_plan(decision, cognitive_input.text)
            if not _planner.plan_is_effect_free(plan):
                raise ValueError("plan non conforme (effet potentiel)")
            self._go(CognitiveState.PLANNING)
            self.metrics["processed"] += 1
            if decision.kind == IntentKind.REFUSE:
                self.metrics["refusals"] += 1
            if decision.kind == IntentKind.CLARIFY:
                self.metrics["clarifications"] += 1
                self._go(CognitiveState.CLARIFICATION_REQUIRED)
            else:
                self._go(CognitiveState.READY)
            result = CognitiveResult(output=decision, plan=plan,
                                    states=list(self._trace), state=self.state)
            if self.on_result is not None:
                self.on_result(result)
            return result
        except (CognitiveInputError, ValueError) as exc:
            self.metrics["errors"] += 1
            try:
                self._go(CognitiveState.ERROR)
            except ValueError:
                self.state = CognitiveState.ERROR
                self._trace.append(CognitiveState.ERROR.value)
            raise
