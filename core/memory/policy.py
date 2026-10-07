"""Wilfrid — politique mémoire (triage déterministe, sans autorité).

Décide, avant toute écriture, si une information peut être mémorisée telle
quelle (AUTO), doit être proposée à validation humaine (PROPOSE) ou doit être
refusée (REFUSE). La politique ne crée ni droit, ni permission, ni mandat :
elle filtre des données. Règles explicites et fermées :

- REFUSE : secret apparent (même famille d'indices que le garde de
  `store.py`, sans importer son privé) ou prétention d'autorité
  (liste fermée de formulations) ;
- PROPOSE : marqueurs d'incertitude explicites ;
- AUTO : tout le reste (y compris contenu hostile générique, qui reste
  une donnée inerte une fois stocké — la garde porte sur secrets et
  autorité, pas sur le désagrément).
"""

from __future__ import annotations

from typing import Any, Tuple

_SECRET_HINTS = ("secret", "credential", "passwd", "api_key", "apikey",
                 "bearer", "-----begin", "token", "motdepasse=")

_AUTHORITY_CLAIMS = (
    "autorise", "autorisé", "autorisée", "approuve", "approuvé",
    "approbation accordée", "permission accordée", "mandat actif",
    "monsieur k a autorisé", "monsieur k a dit",
    "droit de", "pleins pouvoirs",
)

_UNCERTAINTY_MARKERS = (
    "peut-être", "probablement", "sans doute", "il paraît", "il semble",
    "peut etre", "?",
)

_EPHEMERAL_DEFAULT_TTL_DAYS = 1.0


def _contains(haystack: str, markers: Tuple[str, ...]) -> bool:
    lowered = haystack.lower()
    compact = lowered.replace(" ", "").replace("\t", "")
    return any(marker in lowered or marker.replace(" ", "") in compact
               for marker in markers)


def classify(kind: Any, content: Any) -> Tuple[str, str]:
    """Trie une écriture candidate : AUTO / PROPOSE / REFUSE + motif."""
    if not isinstance(kind, str) or not kind.strip():
        return "REFUSE", "categorie-invalide"
    if not isinstance(content, str) or not content.strip():
        return "REFUSE", "contenu-invalide"
    if _contains(content, _SECRET_HINTS):
        lowered = content.lower()
        compact = lowered.replace(" ", "").replace("\t", "")
        if "-----begin" in lowered and "private" in lowered:
            return "REFUSE", "secret-detecte"
        for hint in ("api_key=", "apikey=", "bearer", "password=",
                     "passwd=", "motdepasse=", "token=", "credentials"):
            if hint in compact:
                return "REFUSE", "secret-detecte"
    if _contains(content, _AUTHORITY_CLAIMS):
        return "REFUSE", "pretention-autorite"
    if _contains(content, _UNCERTAINTY_MARKERS):
        return "PROPOSE", "incertitude-explicite"
    return "AUTO", "ok"


def default_ttl_days(kind: Any) -> Any:
    """TTL par défaut : éphémère borné, sinon aucun (pas de TTL universel)."""
    if kind == "ephemeral":
        return _EPHEMERAL_DEFAULT_TTL_DAYS
    return None
