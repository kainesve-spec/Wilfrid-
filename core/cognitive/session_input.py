"""Wilfrid — pont session → cognition (K1) : tour brut vers intention routée.

Chaîne : tour session brut → `CognitiveInput` → `CognitiveCore.process()` →
`CognitiveOutput` → `dispatch()` → `DispatchResult` (Request gouvernable ou
NO_ROUTE). N'appelle JAMAIS le Governor : la requête produite attend une
approbation humaine et reste DENY sans elle.

Garanties (K1-1..K1-10) : aucune autorité/approbation créée, aucune exécution,
aucune cible devinée, texte vide → NO_ROUTE, aucun tour exploitable → NO_ROUTE,
déterministe, aucun I/O, aucune dépendance nouvelle, frontière P7 inchangée.
Ne connaît aucune implémentation interne de Session (données nues uniquement,
aucun import de `core.session` : isolation P4 intacte).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.cognitive.core import CognitiveCore
from core.cognitive.dispatch import DispatchResult, dispatch
from core.cognitive.types import CognitiveOutput

USER_ROLE = "user"
MAX_TURNS_SCANNED = 20


@dataclass(frozen=True)
class TurnResult:
    """Issue du pont : ROUTED (intention + demande typée) ou NO_ROUTE motivé."""

    status: str
    text: str = ""
    cognitive_output: Optional[CognitiveOutput] = None
    dispatch_result: Optional[DispatchResult] = None
    reason: str = ""


def select_user_text(turns: Any) -> Optional[str]:
    """Dernier tour `user` non vide, sans jamais deviner depuis un autre champ."""
    if not isinstance(turns, list):
        return None
    selected: Optional[str] = None
    for turn in turns[:MAX_TURNS_SCANNED]:
        if not isinstance(turn, dict):
            continue
        if turn.get("role") != USER_ROLE:
            continue
        text = turn.get("text")
        if isinstance(text, str) and text.strip():
            selected = text.strip()
    return selected


def run_turn(turns: Any, session_id: Any, now: Any, source: Any, *,
             skill_id: str = "wilfrid-core", skill_version: str = "1.0",
             request_id: str = "") -> TurnResult:
    """Exécute la chaîne complète tour → intention → demande typée."""
    if not isinstance(session_id, str) or not session_id:
        return TurnResult("NO_ROUTE", "", None, None, "invalid-session-id")
    if not isinstance(source, str) or not source:
        return TurnResult("NO_ROUTE", "", None, None, "invalid-source")
    if not isinstance(now, (int, float)) or now != now:
        return TurnResult("NO_ROUTE", "", None, None, "invalid-timestamp")
    text = select_user_text(turns)
    if text is None:
        return TurnResult("NO_ROUTE", "", None, None, "no-usable-user-turn")
    snapshot = [dict(t) for t in turns[:MAX_TURNS_SCANNED]
                if isinstance(t, dict)]
    try:
        core = CognitiveCore()
        result = core.process(text, session_id, snapshot, float(now), source)
    except (ValueError, TypeError) as exc:
        return TurnResult("NO_ROUTE", text, None, None,
                          f"cognitive-error:{type(exc).__name__}")
    dispatch_result = dispatch(result.output, skill_id=skill_id,
                               skill_version=skill_version,
                               request_id=request_id)
    status = "ROUTED" if dispatch_result.status == "ROUTED" else "NO_ROUTE"
    return TurnResult(status, text, result.output, dispatch_result,
                      dispatch_result.reason or "ok")
