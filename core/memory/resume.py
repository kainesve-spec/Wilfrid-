"""Wilfrid — reprise gouvernée (contexte mémorisé, autorité revalidée).

`resume()` reconstruit un contexte utilisable depuis la mémoire SANS jamais
en dériver d'autorisation : SAVE → LOAD → VALIDATE → REVALIDATE AUTHORITY →
RESUME. Les états d'autorité (mandats) sont fournis par l'appelant comme
État actuel (`mandates={"id": "ACTIVE"|...}`) ; toute référence à un mandat
(`provenance_ref == "mandate:<id>"`) est confrontée à cet état :
révoqué/expiré → BLOCKED (définitif) ; suspendu ou état inconnu →
DEFERRED (rejouable) ; absent de la table → DEFERRED (invérifiable).
Règle finale : ÉTAT ACTUEL + AUTORISATION ACTUELLE > MÉMOIRE HISTORIQUE ;
en cas d'incertitude : ni invention, ni exécution, incertitude signalée.

Contradictions : deux enregistrements actifs partageant la même
`provenance_ref` non vide avec des contenus différents sont signalés comme
paire potentiellement contradictoire (heuristique de surface explicite),
conservés tous deux, jamais arbitrés.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.memory.store import MemoryStore

STATUSES = ("READY", "DEFERRED", "BLOCKED")
_TERMINAL_MANDATES = ("REVOKED", "EXPIRED")


@dataclass(frozen=True)
class ResumeResult:
    """Issue de reprise : contexte + explicitations, jamais d'autorisation."""

    status: str = "DEFERRED"
    context: Tuple[Dict[str, Any], ...] = ()
    stale: Tuple[str, ...] = ()
    invalidated: Tuple[str, ...] = ()
    contradictions: Tuple[Tuple[str, str], ...] = ()
    mandates_checked: Tuple[Tuple[str, str], ...] = ()
    reason: str = ""


def _mandate_ref(record: Any) -> Optional[str]:
    ref = getattr(record, "provenance_ref", "") or ""
    if isinstance(ref, str) and ref.startswith("mandate:"):
        identifier = ref[len("mandate:"):].strip()
        if identifier:
            return identifier
    return None


def resume(store: Any, *, session_id: str = "",
           mandates: Optional[Dict[str, str]] = None,
           now: Any = None, limit: int = 10) -> ResumeResult:
    """Reconstruit un contexte reprenable depuis la mémoire persistante."""
    if not isinstance(store, MemoryStore):
        return ResumeResult(status="DEFERRED", reason="magasin-invalide")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return ResumeResult(status="DEFERRED", reason="limite-invalide")
    if mandates is not None and not isinstance(mandates, dict):
        return ResumeResult(status="DEFERRED", reason="autorite-invalide")
    try:
        rows = store.list_active(limit=100) + store.list_active(
            limit=100, statuses=("invalidated",))
    except Exception:
        return ResumeResult(status="DEFERRED", reason="lecture-impossible")
    moment = now
    usable, stale, invalidated = [], [], []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if session_id and str(row.get("session_id", "")) not in ("",
                                                                 session_id):
            continue
        try:
            record = store.read(str(row.get("id", "")), now=moment)
        except Exception:
            continue
        if record is None:
            continue
        if record.status == "invalidated":
            invalidated.append(record.id)
        elif record.freshness == "EXPIRED":
            stale.append(record.id)
        elif record.status == "active":
            usable.append(record)
    usable.sort(key=lambda record: record.id)
    usable = usable[:limit]
    by_ref: Dict[str, List[str]] = {}
    contents: Dict[str, str] = {}
    for record in usable:
        if record.provenance_ref and record.provenance_ref != "":
            by_ref.setdefault(record.provenance_ref, []).append(record.id)
            contents[record.id] = record.content
    contradictions = tuple(sorted(
        (pair[0], pair[1])
        for ids in by_ref.values() if len(ids) > 1
        for pair in [tuple(sorted(ids)[:2])]
        if len({contents.get(i, "") for i in pair}) > 1)[:10]
    )
    checked: List[Tuple[str, str]] = []
    refs = sorted({_mandate_ref(record) for record in usable}
                  - {None})  # type: ignore[misc]
    refs = [ref for ref in refs if isinstance(ref, str)]
    if refs and mandates is None:
        return ResumeResult(
            status="DEFERRED", reason="autorite-inverifiable",
            stale=tuple(stale), invalidated=tuple(invalidated),
            contradictions=contradictions)
    for ref in refs:
        state = mandates.get(ref, "") if mandates else ""
        checked.append((ref, state if state else "inconnu"))
        if state in _TERMINAL_MANDATES:
            return ResumeResult(
                status="BLOCKED", reason=f"mandat-{state.lower()}",
                stale=tuple(stale), invalidated=tuple(invalidated),
                contradictions=contradictions,
                mandates_checked=tuple(checked))
        if state != "ACTIVE":
            return ResumeResult(
                status="DEFERRED", reason="mandat-non-actif",
                stale=tuple(stale), invalidated=tuple(invalidated),
                contradictions=contradictions,
                mandates_checked=tuple(checked))
    if not usable:
        if stale or invalidated:
            return ResumeResult(status="DEFERRED",
                                reason="contexte-obsolete",
                                stale=tuple(stale),
                                invalidated=tuple(invalidated),
                                contradictions=contradictions,
                                mandates_checked=tuple(checked))
        return ResumeResult(status="READY", reason="sans-memoire",
                            stale=tuple(stale),
                            invalidated=tuple(invalidated),
                            contradictions=contradictions,
                            mandates_checked=tuple(checked))
    context = tuple(
        {"record_id": record.id, "kind": record.kind,
         "text": record.content, "freshness": record.freshness,
         "provenance": record.provenance_source} for record in usable)
    return ResumeResult(status="READY", context=context, stale=tuple(stale),
                        invalidated=tuple(invalidated),
                        contradictions=contradictions,
                        mandates_checked=tuple(checked), reason="ok")
