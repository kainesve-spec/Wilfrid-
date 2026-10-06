"""Wilfrid — taxonomie et types P5 (fermés, immuables, versionnés)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

TAXONOMY_VERSION = "1.0"
MAX_TEXT_CHARS = 2000


class IntentKind(str, Enum):
    """Huit catégories, ni plus ni moins. Aucune neuvième implicite."""

    DIRECT = "DIRECT"
    CLARIFY = "CLARIFY"
    PLAN = "PLAN"
    NEED_SEARCH = "NEED_SEARCH"
    NEED_TOOL = "NEED_TOOL"
    NEED_ACTION = "NEED_ACTION"
    REFUSE = "REFUSE"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class CognitiveInput:
    """Entrée bornée et validée (snapshot déjà copié en profondeur)."""

    text: str
    session_id: str
    context_snapshot: List[Dict[str, Any]]
    timestamp: float
    source: str
    stt_confidence: Optional[float] = None


@dataclass(frozen=True)
class CognitiveParams:
    """Paramètres simples extraits : données uniquement, jamais exécutés."""

    action: str = ""
    objet: str = ""
    cible: str = ""
    question: str = ""
    etapes: List[str] = field(default_factory=list)
    outil: str = ""
    besoin_recherche: str = ""


@dataclass(frozen=True)
class CognitiveOutput:
    """Décision structurée. NEED_ACTION = intention déclarée, sans exécution."""

    kind: IntentKind
    params: CognitiveParams = field(default_factory=CognitiveParams)
    confidence: float = 0.0
    missing: List[str] = field(default_factory=list)
