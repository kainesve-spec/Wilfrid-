"""Wilfrid — classifieur déterministe P5 (règles + regex, français).

Premier motif applicable gagne (ordre documenté ci-dessous) :
  vide → remplissage → refus → rappel incomplet → DIRECT →
  NEED_TOOL → PLAN → NEED_ACTION → NEED_SEARCH → contradiction →
  UNCERTAIN (repli).
Aucun LLM, modèle, réseau, embedding ou apprentissage. Même entrée →
même sortie. En cas de doute : CLARIFY (manque) ou UNCERTAIN (sens).
"""

from __future__ import annotations

import re

from core.cognitive.types import CognitiveOutput, CognitiveParams, IntentKind

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüçœæ]+")

_FILLERS = frozenset({"euh", "hmm", "hum", "heu", "hein"})

_REFUSE_PATTERNS = (
    "pirater", "hacker", "cracker", "voler", "tuer", "assassin",
    "bombe", "arme", "drogue", "suicide", "ransomware",
    "mot de passe", "clé api", "cle api", "api key", "code secret",
)

_ACTION_VERBS = (
    "ouvre", "ouvrez", "lance", "lancez", "joue", "jouez",
    "envoie", "envoyez", "appelle", "appelez", "mets", "mettez",
    "supprime", "supprimez", "crée", "créez", "éteins", "éteignez",
    "allume", "allumez", "règle", "réglez", "ferme", "fermez",
    "démarre", "démarrez", "compose", "composez",
)

_ARTICLES = frozenset({"un", "une", "le", "la", "les", "des", "du", "de",
                       "au", "aux", "mon", "ma", "mes", "ton", "ta", "tes"})

_TOOL_TIME = ("heure", "date", "jour", "aujourd")
_TOOL_COMPUTE = ("calcule", "calcul", "combien font", "multiplié",
                 "multiplie", "divisé", "divise", "additionne",
                 "soustrait", "fois", "+", "*", "/", "=")

_PLAN_MARKERS = ("étape par étape", "etapes", "plusieurs étapes",
                 "organise", "organiser", "prépare", "préparer",
                 "planifie", "planifier", "programme", "programmer")

_SEARCH_IMPERATIVE = ("explique", "expliques", "explique-moi", "définis",
                     "raconte", "résume", "décris")
_SEARCH_QUESTIONS = ("quel", "quelle", "quels", "quelles", "pourquoi",
                     "comment", "qu'est-ce", "qu est-ce",
                     "définition", "qui",
                     "quoi", "où", "quand", "combien")
_SEARCH_TOPICS = ("temps", "météo", "meteo", "pluie", "capitale")

_GREETINGS = ("bonjour", "bonsoir", "salut", "coucou", "hello", "yo")
_IDENTITY = ("qui es-tu", "qui etes-tu", "qui êtes-vous", "ton nom",
             "votre nom", "présente-toi", "presente-toi")
_CAPABILITY = ("sais-tu faire", "sais tu faire", "peux-tu faire",
               "peux tu faire", "tes capacités", "tes capacites",
               "liste des commandes")
_THANKS = ("merci",)


def _words(text: str) -> list:
    return _WORD_RE.findall(text.lower())


def _direct(text: str, words: list) -> CognitiveOutput | None:
    lowered = text.lower()
    joined = " ".join(words)
    if any(g == w for g in _GREETINGS for w in words) and len(words) <= 4:
        return CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                               0.90, [])
    if any(p in lowered for p in _IDENTITY):
        return CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                               0.90, [])
    if any(p in lowered for p in _CAPABILITY):
        return CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                               0.85, [])
    if any(w in _THANKS for w in words):
        return CognitiveOutput(IntentKind.DIRECT, CognitiveParams(),
                               0.90, [])
    _ = joined
    return None


def _extract_after_verb(words: list, verbs: tuple) -> tuple[str, str]:
    """Objet (mot plein après le verbe) et cible (nom propre après préposition)."""
    objet, cible = "", ""
    for i, word in enumerate(words):
        if word in verbs:
            following = words[i + 1:]
            meaningful = [w for w in following if w not in _ARTICLES]
            if meaningful:
                objet = meaningful[0]
            break
    return objet, cible


def _extract_cible(raw_text: str) -> str:
    match = re.search(
        r"\b(?:à|chez|pour|vers|de|avec)\s+([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ][\wàâäéèêëîïôöùûüçœæ-]*)",
        raw_text)
    return match.group(1) if match else ""


def classify(text: str) -> CognitiveOutput:
    """Classifie un texte brut déjà validé (longueur vérifiée en amont)."""
    stripped = text.strip()
    if not stripped:
        return CognitiveOutput(IntentKind.CLARIFY, CognitiveParams(),
                               0.95, ["text"])
    words = _words(stripped)
    if not any(len(w) >= 2 for w in words):
        return CognitiveOutput(IntentKind.CLARIFY, CognitiveParams(),
                               0.90, ["text"])
    if words and all(w in _FILLERS for w in words):
        return CognitiveOutput(IntentKind.CLARIFY, CognitiveParams(),
                               0.85, ["text"])
    lowered = stripped.lower()
    if any(p in lowered for p in _REFUSE_PATTERNS):
        return CognitiveOutput(IntentKind.REFUSE, CognitiveParams(),
                               0.95, [])
    if "rappel" in words or "rappelle" in words:
        meaningful = [w for w in words
                      if w not in _ARTICLES and w not in ("mets", "mettre")]
        if len(meaningful) <= 2:
            return CognitiveOutput(
                IntentKind.CLARIFY,
                CognitiveParams(action="rappel"), 0.80, ["objet"])
    direct = _direct(stripped, words)
    if direct is not None:
        return direct
    if any(t in lowered for t in _TOOL_TIME) and (
            "?" in stripped or any(q in lowered for q in ("quelle", "quel"))):
        outil = "horloge" if any(
            t in lowered for t in ("heure", "date", "jour")) else "outil_temps"
        return CognitiveOutput(IntentKind.NEED_TOOL,
                               CognitiveParams(outil=outil), 0.85, [])
    if any(t in lowered for t in _TOOL_COMPUTE):
        return CognitiveOutput(IntentKind.NEED_TOOL,
                               CognitiveParams(outil="calcul"), 0.85, [])
    if any(p in lowered for p in _PLAN_MARKERS):
        return CognitiveOutput(IntentKind.PLAN, CognitiveParams(),
                               0.80, [])
    verb_hit = next((w for w in words if w in _ACTION_VERBS), "")
    if verb_hit:
        objet, _ignored = _extract_after_verb(words, _ACTION_VERBS)
        cible = _extract_cible(stripped)
        return CognitiveOutput(IntentKind.NEED_ACTION,
                               CognitiveParams(action=verb_hit, objet=objet,
                                               cible=cible), 0.85, [])
    if ("?" in stripped and any(q in lowered for q in _SEARCH_QUESTIONS)) \
            or any(t in lowered for t in _SEARCH_TOPICS) \
            or any(v in lowered for v in _SEARCH_IMPERATIVE):
        question = stripped if stripped.endswith("?") else ""
        return CognitiveOutput(
            IntentKind.NEED_SEARCH,
            CognitiveParams(question=question,
                            besoin_recherche=stripped[:200]), 0.80, [])
    wordset = set(words)
    if ({"oui", "non"} <= wordset) or ({"jamais", "toujours"} <= wordset):
        return CognitiveOutput(IntentKind.UNCERTAIN, CognitiveParams(),
                               0.40, [])
    return CognitiveOutput(IntentKind.UNCERTAIN, CognitiveParams(), 0.30, [])
