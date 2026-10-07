"""Wilfrid — routage intention → capability (interprétation, sans autorité).

Composant isolé et déterministe : normalisation contrôlée, synonymes
explicites français, correspondances exactes/structurées, extraction des
paramètres explicitement présents, détection d'ambiguïté. Ne crée ni
capability, ni permission, ni autorité, ni approbation ; n'exécute rien ;
n'élargit et n'invente rien. Seul MATCH suffisamment certain poursuit vers
la gouvernance existante ; AMBIGUOUS/MISSING_INFORMATION → clarification ;
NO_MATCH → réponse honnête d'absence. Le texte utilisateur (y compris toute
prétendue approbation) reste une donnée sans effet sur les règles.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

STATUSES = ("MATCH", "AMBIGUOUS", "NO_MATCH", "MISSING_INFORMATION")

# Catalogue fermé : les 4 capabilities B2 réellement présentes. Les listes
# de mots sont des données de correspondance explicites, modifiables sans
# toucher à l'autorité (qui vit dans Governor/Approval Gate/registre).
ENTRIES: Tuple[Dict[str, Any], ...] = (
    {"id": "P7.CATALOG_READ", "keywords": (
        "catalogue", "capacites", "capabilites", "aide", "aider",
        "sais-tu-faire", "sais-tu faire", "liste", "lister",
        "fonctionnalites", "fonctionnalités", "que faire"),
     "requires_param": False, "param_kind": ""},
    {"id": "P7.JAIL_READ", "keywords": (
        "lis", "lire", "lecture", "lisez", "contenu"),
     "requires_param": True, "param_kind": "filename"},
    {"id": "P7.JAIL_WRITE_REVERSIBLE", "keywords": (
        "ecris", "écrire", "ecrire", "note", "noter", "ajoute", "ajouter",
        "sauvegarde", "sauvegarder", "enregistre", "enregistrer",
        "redige", "rédige"),
     "requires_param": True, "param_kind": "filename_and_content"},
    {"id": "P7.NOTIFY_LOCAL", "keywords": (
        "notifie", "notifier", "notification", "previens", "préviens",
        "prevenir", "prévenir", "alerte", "alerter", "rappelle",
        "rappeler", "rappel", "dis-moi", "dis moi", "annonce", "annoncer"),
     "requires_param": True, "param_kind": "message"},
)

_FILENAME_RE = re.compile(
    r"(?:fichier|note|document)\s+(?:nomm[ée]e?\s+)?[\"«]?"
    r"([A-Za-z0-9_\-.éèêàçûôîâ]+)")
_UNSAFE_PARAM_RE = re.compile(r"(\.\.|/|\\\\)")


@dataclass(frozen=True)
class RouteResult:
    """Issue du routage : statut fermé + candidate éventuelle, sans autorité."""

    status: str = "NO_MATCH"
    intent: str = ""
    capability_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reason: str = ""
    request_id: str = ""


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = re.sub(r"\.{2,}", " ", folded)
    folded = re.sub(r"[^\w\s\-/…\"'«»]", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _request_id(text: str) -> str:
    return "rt-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _keyword_hits(normalized: str, keywords: Tuple[str, ...]) -> bool:
    """Présence par mot entier (jamais par sous-chaîne : notes ≠ note)."""
    tokens = set(normalized.split())
    for keyword in keywords:
        if not isinstance(keyword, str) or not keyword:
            continue
        if " " in keyword:
            if re.search(r"\b" + re.escape(keyword) + r"\b", normalized):
                return True
        elif keyword in tokens:
            return True
    return False


def _entry_matches(normalized: str, entry_id: str,
                   keywords: Tuple[str, ...]) -> str:
    """Niveau : exact (ID mentionné tel quel) > mot-clé. Vide sinon.

    Correspondance par mot entier uniquement : « notes » ne déclenche jamais
    « note ». Aucun score, aucun choix statistique.
    """
    if entry_id.lower() in normalized.split():
        return "exact"
    if _keyword_hits(normalized, keywords):
        return "keyword"
    return ""


def _extract_filename(normalized: str) -> Optional[str]:
    match = _FILENAME_RE.search(normalized)
    if match is None:
        return None
    name = match.group(1).strip(".-")
    if not name or _UNSAFE_PARAM_RE.search(name):
        return None
    return name


def _extract_content(normalized: str) -> Optional[str]:
    for opener, closer in (('"', '"'), ("«", "»"), ("'", "'")):
        start = normalized.find(opener)
        if start >= 0:
            end = normalized.find(closer, start + 1)
            if end > start + 1:
                return normalized[start + 1:end].strip()[:280]
    return None


def _extract_message(normalized: str, keywords: Tuple[str, ...]) -> Optional[str]:
    quoted = _extract_content(normalized)
    if quoted:
        return quoted
    remainder = normalized
    for keyword in sorted(keywords, key=len, reverse=True):
        remainder = remainder.replace(keyword, " ")
    remainder = re.sub(r"\s+", " ", remainder).strip(" .,:;!?-")
    if not remainder or len(remainder) > 280:
        return None
    return remainder


def route(text: Any, entries: Any = None,
          context: Any = None) -> RouteResult:
    """Route un texte vers une capability candidate. Pur et déterministe."""
    del context
    table = ENTRIES if entries is None else entries
    if not isinstance(text, str):
        return RouteResult(status="NO_MATCH", reason="texte-invalide",
                           request_id=_request_id(""))
    rid = _request_id(text)
    normalized = _normalize(text)
    if not normalized:
        return RouteResult(status="NO_MATCH", reason="texte-vide",
                           request_id=rid)
    if not isinstance(table, (tuple, list)):
        return RouteResult(status="NO_MATCH", reason="catalogue-invalide",
                           request_id=rid)
    hits: List[Tuple[Dict[str, Any], str]] = []
    for entry in table:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id", "")
        keywords = entry.get("keywords", ())
        if not entry_id or not isinstance(keywords, (tuple, list)):
            continue
        level = _entry_matches(normalized, str(entry_id),
                               tuple(keywords))
        if level:
            hits.append((entry, level))
    if not hits:
        return RouteResult(status="NO_MATCH", reason="aucune-correspondance",
                           request_id=rid)
    if len(hits) > 1:
        return RouteResult(
            status="AMBIGUOUS", intent="ambigu",
            reason="plusieurs-capabilities:" + ",".join(
                sorted(entry.get("id", "") for entry, _ in hits)),
            request_id=rid)
    entry, level = hits[0]
    entry_id = str(entry.get("id", ""))
    intent = "lecture" if "READ" in entry_id else (
        "ecriture" if "WRITE" in entry_id else (
            "notification" if "NOTIFY" in entry_id else "information"))
    confidence = 1.0 if level == "exact" else 0.8
    if not entry.get("requires_param", False):
        return RouteResult(status="MATCH", intent=intent,
                           capability_id=entry_id, params={},
                           confidence=confidence,
                           reason="correspondance-" + level, request_id=rid)
    kind = str(entry.get("param_kind", ""))
    if kind == "filename":
        name = _extract_filename(normalized)
        if name is None:
            return RouteResult(
                status="MISSING_INFORMATION", intent=intent,
                capability_id=entry_id, confidence=confidence,
                reason="nom-fichier-manquant", request_id=rid)
        return RouteResult(status="MATCH", intent=intent,
                           capability_id=entry_id,
                           params={"filename": name}, confidence=confidence,
                           reason="correspondance-" + level, request_id=rid)
    if kind == "filename_and_content":
        name = _extract_filename(normalized)
        content = _extract_content(normalized)
        if name is None or not content:
            return RouteResult(
                status="MISSING_INFORMATION", intent=intent,
                capability_id=entry_id, confidence=confidence,
                reason="nom-ou-contenu-manquant", request_id=rid)
        return RouteResult(status="MATCH", intent=intent,
                           capability_id=entry_id,
                           params={"filename": name, "content": content},
                           confidence=confidence,
                           reason="correspondance-" + level, request_id=rid)
    if kind == "message":
        message = _extract_message(
            normalized, tuple(entry.get("keywords", ())))
        if not message:
            return RouteResult(
                status="MISSING_INFORMATION", intent=intent,
                capability_id=entry_id, confidence=confidence,
                reason="message-manquant", request_id=rid)
        return RouteResult(status="MATCH", intent=intent,
                           capability_id=entry_id,
                           params={"message": message}, confidence=confidence,
                           reason="correspondance-" + level, request_id=rid)
    return RouteResult(status="NO_MATCH", intent=intent,
                       capability_id=entry_id, confidence=confidence,
                       reason="parametrage-inconnu", request_id=rid)
