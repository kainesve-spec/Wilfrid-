"""Wilfrid — pont P5 → P7 (capability resolution), tranche P6.1.

Convertit une intention P5 déclarative (NEED_ACTION / NEED_TOOL) en demande
typée P7 (`Request`) lorsque l'outil/l'action correspond EXACTEMENT à une
entrée du catalogue. Fonction pure : aucun I/O, réseau, FS, effet.

Garanties :
- ne crée JAMAIS d'`Approval` (aucune autorité conférée) ;
- ne devine JAMAIS de cible (défaut NO_ROUTE motivé) ;
- bornes et durées reprises du catalogue / B2, jamais du texte utilisateur ;
- kinds non routables (DIRECT, CLARIFY, PLAN, NEED_SEARCH, REFUSE, UNCERTAIN)
  et outils inconnus/ambigus/vides → NO_ROUTE + motif explicite.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.cognitive.types import CognitiveOutput, IntentKind
from core.p7.catalog import build_catalog, lookup, scope_for
from core.p7.types import (
    MAX_DURATION_S,
    MAX_LIMITS,
    Request,
)

ROUTABLE_KINDS = (IntentKind.NEED_ACTION, IntentKind.NEED_TOOL)


@dataclass(frozen=True)
class DispatchResult:
    """Issue du routage : ROUTED (request typée, sans approbation) ou NO_ROUTE."""

    status: str
    request: Optional[Request] = None
    reason: str = ""


def _clean(text: Any) -> str:
    return str(text or "").strip()


def dispatch(output: Any, *, skill_id: str = "wilfrid-core",
             skill_version: str = "1.0",
             request_id: str = "") -> DispatchResult:
    """Route une intention P5 vers une `Request` P7, ou NO_ROUTE motivé."""
    if not isinstance(output, CognitiveOutput):
        return DispatchResult("NO_ROUTE", None, "invalid-output")
    if output.kind not in ROUTABLE_KINDS:
        return DispatchResult("NO_ROUTE", None,
                              f"kind-not-routable:{output.kind.value}")
    raw_tool = _clean(output.params.outil) or _clean(output.params.action)
    if not raw_tool or len(raw_tool) > 128:
        return DispatchResult("NO_ROUTE", None, "empty-or-oversize-tool")
    catalog = build_catalog()
    found, _, entry = lookup(catalog, raw_tool)
    if not found or entry is None:
        return DispatchResult("NO_ROUTE", None, "unknown-tool")
    permission_id = entry.id
    scope = scope_for(entry.id)
    target = entry.id
    limits: Dict[str, Any] = dict(MAX_LIMITS.get(permission_id, {}))
    duration = int(MAX_DURATION_S.get(permission_id, 0))
    seed = f"{output.kind.value}|{entry.id}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()[:8]
    rid = _clean(request_id) or f"dispatch-{digest}"
    request = Request(
        request_id=rid[:64],
        skill_id=_clean(skill_id)[:64] or "wilfrid-core",
        skill_version=_clean(skill_version)[:32] or "1.0",
        permission_id=permission_id,
        scope=scope,
        target=target,
        limits=limits,
        duration_s=duration,
        reason=f"routed:{output.kind.value}",
    )
    return DispatchResult("ROUTED", request, "ok")
