"""Wilfrid — routeur d'effets P7 K-α (façade d'invocation, sans autorité).

Centralise le choix `permission_id → fonction d'effet existante` sans déplacer
l'autorité du Governor : chaque fonction d'effet ré-exécute `G.decide()` et le
routeur ne transforme jamais un DENY en ALLOW. Le routeur ne crée, ne modifie
ni ne contourne aucune Approval, permission, scope, cible ou payload ; toute
donnée obligatoire manquante ou invalide produit un DENY contrôlé, sans effet.

Table de routage statique, explicite et immuable (`MappingProxyType`) : aucune
découverte dynamique, aucun auto-enregistrement, aucun plugin, aucun import
dynamique, aucune convention implicite. Seules les quatre permissions B2 sont
mappées ; toute autre valeur produit un DENY déterministe, sans handler appelé.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from core.p7 import catalog as _catalog
from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import notify as _notify
from core.p7 import reader as _reader
from core.p7 import writer as _writer
from core.p7.journal import Journal
from core.p7.types import Approval, Request


@dataclass(frozen=True)
class InvokeResult:
    """Issue du routage : ROUTED (décision du handler transmise) ou DENY."""

    status: str
    decision: Optional[G.Decision]
    result: Any = None
    reason: str = ""


def _deny(reason: str) -> InvokeResult:
    return InvokeResult("DENY", None, None, reason)


def _call_catalog(*, request: Request, approval: Optional[Approval],
                  now: float, journal: Any,
                  payload: Any, catalog: Any) -> InvokeResult:
    if payload is not None:
        return _deny(E.REQUEST_INVALID)
    available = journal.available() if isinstance(journal, Journal) else False
    if catalog is None:
        catalog = _catalog.build_catalog()
    if not isinstance(catalog, tuple):
        return _deny(E.REQUEST_INVALID)
    decision, result = _catalog.evaluate(request, approval, now, available,
                                         catalog)
    status = "ROUTED" if decision.allowed else "DENY"
    return InvokeResult(status, decision, result, decision.reason)


def _need_journal(journal: Any) -> bool:
    return isinstance(journal, Journal)


def _call_read(*, request: Request, approval: Optional[Approval],
               now: float, journal: Any,
               payload: Any, catalog: Any) -> InvokeResult:
    if payload is not None or catalog is not None:
        return _deny(E.REQUEST_INVALID)
    if not _need_journal(journal):
        return _deny(E.JOURNAL_UNAVAILABLE)
    decision, result = _reader.read_one(request, approval, now, journal)
    status = "ROUTED" if decision.allowed else "DENY"
    return InvokeResult(status, decision, result, decision.reason)


def _call_write(*, request: Request, approval: Optional[Approval],
                now: float, journal: Any,
                payload: Any, catalog: Any) -> InvokeResult:
    if catalog is not None:
        return _deny(E.REQUEST_INVALID)
    if not isinstance(payload, (bytes, bytearray)) or isinstance(payload, bool):
        return _deny(E.REQUEST_INVALID)
    if not _need_journal(journal):
        return _deny(E.JOURNAL_UNAVAILABLE)
    decision, result = _writer.write_one(request, approval, now, journal,
                                         bytes(payload))
    status = "ROUTED" if decision.allowed else "DENY"
    return InvokeResult(status, decision, result, decision.reason)


def _call_notify(*, request: Request, approval: Optional[Approval],
                 now: float, journal: Any,
                 payload: Any, catalog: Any) -> InvokeResult:
    if catalog is not None:
        return _deny(E.REQUEST_INVALID)
    if not isinstance(payload, str):
        return _deny(E.REQUEST_INVALID)
    if not _need_journal(journal):
        return _deny(E.JOURNAL_UNAVAILABLE)
    decision, result = _notify.notify(request, approval, now, journal,
                                      payload)
    status = "ROUTED" if decision.allowed else "DENY"
    return InvokeResult(status, decision, result, decision.reason)


_ROUTES: Mapping[str, Any] = MappingProxyType({
    "P7.CATALOG_READ": _call_catalog,
    "P7.JAIL_READ": _call_read,
    "P7.JAIL_WRITE_REVERSIBLE": _call_write,
    "P7.NOTIFY_LOCAL": _call_notify,
})


def route_ids() -> Tuple[str, ...]:
    """Identifiants routés, dans l'ordre de la table (inspectable)."""
    return tuple(_ROUTES.keys())


def invoke(*, permission_id: Any, request: Any = None,
           approval: Any = None, now: Any = None,
           journal: Any = None, payload: Any = None,
           catalog: Any = None) -> InvokeResult:
    """Route vers la fonction d'effet existante, ou DENY contrôlé, zéro effet.

    Ne fabrique aucune donnée manquante : `request` doit être une `Request`
    dont le `permission_id` égale l'argument, `now` un nombre, et le payload
    le type exact exigé par la route. L'approbation est transmise telle quelle
    (y compris `None`) : c'est le handler, via le Governor, qui décide.
    """
    if not isinstance(permission_id, str) or permission_id not in _ROUTES:
        return _deny(E.PERMISSION_UNKNOWN)
    if not isinstance(request, Request):
        return _deny(E.REQUEST_INVALID)
    if request.permission_id != permission_id:
        return _deny(E.REQUEST_INVALID)
    if not isinstance(now, (int, float)) or isinstance(now, bool):
        return _deny(E.REQUEST_INVALID)
    handler = _ROUTES[permission_id]
    try:
        return handler(request=request, approval=approval, now=now,
                       journal=journal, payload=payload, catalog=catalog)
    except Exception:
        return _deny(E.UNKNOWN_ERROR)
