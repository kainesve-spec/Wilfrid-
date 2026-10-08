"""Wilfrid — recherche web (abstraction, moteur non configuré).

Aucun fournisseur de recherche n'est configuré : `SEARCH_UNAVAILABLE`
honnête. Les URLs explicites restent utilisables via `engine.fetch_url`.
L'abstraction permet d'ajouter des moteurs sans toucher au Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple


@dataclass(frozen=True)
class SearchResult:
    """Issue de recherche : statut fermé, jamais de résultats simulés."""

    status: str = "SEARCH_UNAVAILABLE"
    engine: str = ""
    results: Tuple[Any, ...] = ()
    detail: str = "aucun-moteur-configure"


_ENGINES: Dict[str, Callable[..., SearchResult]] = {}


def register_engine(name: str, fn: Callable[..., SearchResult]) -> bool:
    """Enregistre un moteur (appel explicite uniquement, jamais auto)."""
    if not isinstance(name, str) or not name.strip() or not callable(fn):
        return False
    _ENGINES[name.strip()] = fn
    return True


def search(query: Any, *, engine: str = "",
           max_results: int = 5) -> SearchResult:
    """Recherche via un moteur enregistré, sinon indisponible honnête."""
    if not isinstance(query, str) or not query.strip():
        return SearchResult(detail="requete-invalide")
    if engine and engine in _ENGINES:
        try:
            return _ENGINES[engine](query, max_results=max_results)
        except Exception:
            return SearchResult(status="SEARCH_FAILED", engine=engine,
                                detail="erreur-moteur")
    return SearchResult()


def describe() -> Dict[str, Any]:
    """État recherche (sans effet)."""
    return {"moteurs": sorted(_ENGINES),
            "statut": "SEARCH_UNAVAILABLE" if not _ENGINES else "configure",
            "network": False, "authority": False}
