"""Wilfrid — catalogue déclaratif P7.CATALOG_READ (R0, 0 effet).

Lecture d'une entrée exacte, sans filesystem utilisateur, sans réseau,
sans secret. Ne peut ni accorder une permission, ni modifier une autorisation,
ni déclencher une action, ni modifier P6. Intégration : exécuter `decide()`
d'abord (typing→approval→scope→expiry→limits→journal), puis `lookup()` exact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7.types import Approval, Request

CATALOG_ID = "P7.CATALOG_READ"
MAX_ENTRIES = 50
MAX_BYTES = 8192


@dataclass(frozen=True)
class CatalogEntry:
    """Entrée déclarative : description seule, aucun pouvoir."""

    id: str
    risk: str
    description: str


_CATALOG: Tuple[CatalogEntry, ...] = (
    CatalogEntry("P7.CATALOG_READ", "R0",
                 "Catalogue declare, lecture seule, zero effet."),
    CatalogEntry("P7.JAIL_READ", "R1",
                 "Lecture locale bornee en jail, read-only."),
    CatalogEntry("P7.JAIL_WRITE_REVERSIBLE", "R2",
                 "Ecriture locale unique reversible en jail."),
    CatalogEntry("P7.NOTIFY_LOCAL", "R2",
                 "Notification locale textuelle bornee."),
)


def build_catalog() -> Tuple[CatalogEntry, ...]:
    """Retourne le catalogue déclaratif (copie, jamais de référence mutable)."""
    return tuple(_CATALOG)


def entry_to_dict(entry: CatalogEntry) -> Dict[str, str]:
    return {"id": entry.id, "risk": entry.risk,
            "description": entry.description}


def response_bytes(entry: CatalogEntry) -> int:
    return len(json.dumps(entry_to_dict(entry),
                          ensure_ascii=False).encode("utf-8"))


def list_entries(catalog: Tuple[CatalogEntry, ...],
                 limit: int) -> Tuple[bool, str, Tuple[CatalogEntry, ...]]:
    """Liste bornée : limit>50 ou catalogue>50 = refus (sans effet)."""
    if not isinstance(limit, int) or isinstance(limit, bool):
        return False, E.LIMITS_INVALID, ()
    if limit < 0 or limit > MAX_ENTRIES:
        return False, E.LIMITS_INVALID, ()
    items = tuple(catalog)[:limit]
    if len(items) > MAX_ENTRIES:
        return False, E.LIMITS_INVALID, ()
    total = sum(response_bytes(e) for e in items)
    if total > MAX_BYTES:
        return False, E.LIMITS_INVALID, ()
    return True, "ok", items


def lookup(catalog: Tuple[CatalogEntry, ...],
           entry_id: Any) -> Tuple[bool, str, Optional[CatalogEntry]]:
    """Recherche exacte : voisin/absent/ambigu = introuvable, sans effet."""
    wanted = str(entry_id or "")
    if not wanted or len(wanted) > 512:
        return False, E.REQUEST_INVALID, None
    for entry in catalog:
        if entry.id == wanted:
            if response_bytes(entry) > MAX_BYTES:
                return False, E.LIMITS_INVALID, None
            return True, "ok", entry
    return False, "ENTRÉE_ABSENTE", None


def scope_for(entry_id: str) -> str:
    """Scope exact d'une entrée : 1 périmètre = 1 cible."""
    return f"catalogue:{entry_id}:lecture-seule"


def evaluate(request: Request, approval: Optional[Approval],
             now: float, journal_available: bool,
             catalog: Tuple[CatalogEntry, ...]) -> Tuple[G.Decision, Optional[Dict[str, str]]]:
    """Intégration gouverneur : decide() puis lookup exact, 0 effet FS/réseau."""
    decision = G.decide(request, approval, now, journal_available)
    if not decision.allowed:
        return decision, None
    if request.permission_id != CATALOG_ID:
        deny = G.Decision(False, E.PERMISSION_UNKNOWN,
                          decision.proof)
        return deny, None
    expected_scope = scope_for(request.target)
    if str(request.scope) != expected_scope:
        deny = G.Decision(False, E.SCOPE_NOT_COVERING, decision.proof)
        return deny, None
    found, why, entry = lookup(catalog, request.target)
    if not found or entry is None:
        code = E.SCOPE_NOT_COVERING if why == "ENTRÉE_ABSENTE" else why
        return G.Decision(False, code, decision.proof), None
    return decision, entry_to_dict(entry)
