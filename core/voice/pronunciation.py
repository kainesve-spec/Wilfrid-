"""Wilfrid — préparation vocale du texte (nombres, dictionnaire, acronymes).

Transforme une réponse DÉJÀ VALIDÉE en texte prononçable, sans jamais
modifier le texte affiché ni le sens. Aucune décision, aucune autorité :
données en entrée, données en sortie. Dictionnaire extensible sans toucher
au raisonnement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

_UNITS = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept",
          "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
          "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf")
_TENS = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
         60: "soixante", 100: "cent"}


def _under_hundred(value: int) -> str:
    if value < 20:
        return _UNITS[value]
    if value < 70:
        tens = (value // 10) * 10
        rest = value % 10
        if rest == 0:
            return _TENS[tens]
        if rest == 1:
            return _TENS[tens] + "-et-un"
        return _TENS[tens] + "-" + _UNITS[rest]
    if value < 80:
        if value == 71:
            return "soixante-et-onze"
        return "soixante-" + _under_hundred(value - 60)
    if value == 80:
        return "quatre-vingts"
    return "quatre-vingt-" + _under_hundred(value - 80)


def _under_thousand(value: int) -> str:
    hundreds = value // 100
    rest = value % 100
    if hundreds == 0:
        return _under_hundred(rest)
    head = "cent" if hundreds == 1 else _UNITS[hundreds] + " cent"
    if rest == 0:
        return head + ("s" if hundreds > 1 else "")
    if hundreds > 1:
        head = _UNITS[hundreds] + " cent"
    return head + " " + _under_hundred(rest)


def int_to_french(value: int) -> str:
    """Entier 0..999 999 999 en toutes lettres (français standard)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("entier-invalide")
    if value < 0 or value > 999999999:
        raise ValueError("hors-bornes")
    if value < 1000:
        return _under_thousand(value)
    if value < 1000000:
        thousands = value // 1000
        rest = value % 1000
        head = "mille" if thousands == 1 else _under_thousand(thousands) \
            + " mille"
        if rest == 0:
            return head
        return head + " " + _under_thousand(rest)
    millions = value // 1000000
    rest = value % 1000000
    head = "un million" if millions == 1 else int_to_french(millions) \
        + " millions"
    if rest == 0:
        return head
    if rest < 1000:
        return head + " " + _under_thousand(rest)
    return head + " " + int_to_french(rest)


_MONTHS = {1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai",
           6: "juin", 7: "juillet", 8: "août", 9: "septembre",
           10: "octobre", 11: "novembre", 12: "décembre"}

DEFAULT_DICTIONARY: Dict[str, str] = {
    "Wilfrid": "Wilfrid",
    "TAIOS": "T A I O S",
    "QanXorus": "Q A N X O R U S",
    "USDT": "U S D T",
    "Monsieur K": "Monsieur K",
}


@dataclass
class PreparedSpeech:
    """Texte affiché inchangé + texte à vocaliser + substitutions tracées."""

    display: str = ""
    spoken: str = ""
    substitutions: List[Tuple[str, str]] = field(default_factory=list)


def _spell_letters(word: str) -> str:
    return " ".join(word.upper())


def _decimal_word(decimals: str) -> str:
    if len(decimals) > 2 or (len(decimals) > 1
                             and decimals.startswith("0")):
        return " ".join(_UNITS[int(digit)] for digit in decimals)
    value = int(decimals)
    if value < 20:
        return _UNITS[value]
    if value < 100:
        return _under_hundred(value)
    return int_to_french(value)


def normalize_numbers(text: str,
                      subs: List[Tuple[str, str]]) -> str:
    """Nombres FR : milliers, décimales à virgule/point, pourcentages."""
    text = re.sub(r"(\d+)\.(\d+)(?![\d.])",
                  lambda m: "%s virgule %s" % (m.group(1), m.group(2)),
                  text)
    pattern = re.compile(r"\d(?:[\d ]*\d)?")
    out: List[str] = []
    last = 0
    for match in pattern.finditer(text):
        if match.start() < last:
            continue
        raw = match.group(0)
        compact = raw.replace(" ", "")
        if not compact.isdigit():
            continue
        value = int(compact)
        rest = text[match.end():]
        spoken = int_to_french(value)
        decimal = re.match(r",(\d+)(?!\d)", rest)
        if decimal and len(decimal.group(1)) != 3:
            dec_word = _decimal_word(decimal.group(1))
            spoken = int_to_french(value) + " virgule " + dec_word
            end = match.end() + 1 + len(decimal.group(1))
            after = re.match(r"\s*%", text[end:])
            if after:
                spoken += " pour cent"
                end += len(after.group(0))
            out.append(text[last:match.start()])
            subs.append((text[match.start():end], spoken))
            out.append(spoken)
            last = end
            continue
        percent = re.match(r"\s*%", rest)
        if percent:
            spoken = int_to_french(value) + " pour cent"
            end = match.end() + len(percent.group(0))
            out.append(text[last:match.start()])
            subs.append((text[match.start():end], spoken))
            out.append(spoken)
            last = end
            continue
        thousand = re.match(r",(\d{3})(?!\d)", rest)
        if thousand:
            value = value * 1000 + int(thousand.group(1))
            spoken = int_to_french(value)
            end = match.end() + 4
            out.append(text[last:match.start()])
            subs.append((text[match.start():end], spoken))
            out.append(spoken)
            last = end
            continue
        out.append(text[last:match.start()])
        subs.append((raw, spoken))
        out.append(spoken)
        last = match.end()
    out.append(text[last:])
    return "".join(out)


def normalize_dates_times(text: str,
                          subs: List[Tuple[str, str]]) -> str:
    """Dates jj/mm/aaaa et heures 20h30 (français)."""

    def date_word(match: re.Match) -> str:
        day, month, year = int(match.group(1)), int(match.group(2)), \
            int(match.group(3))
        if not 1 <= day <= 31 or not 1 <= month <= 12:
            return match.group(0)
        spoken = "%s %s %s" % (int_to_french(day), _MONTHS[month],
                               int_to_french(year))
        subs.append((match.group(0), spoken))
        return spoken

    def hour_word(match: re.Match) -> str:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if hour > 23 or minute > 59:
            return match.group(0)
        spoken = "%s heures" % int_to_french(hour)
        if minute:
            spoken += " " + int_to_french(minute)
        subs.append((match.group(0), spoken))
        return spoken

    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", date_word, text)
    text = re.sub(r"\b(\d{1,2})h(\d{2})?\b", hour_word, text)
    return text


def normalize_currency(text: str, subs: List[Tuple[str, str]]) -> str:
    """Symboles monétaires courants (texte affiché inchangé par ailleurs)."""
    table = (("€", "euros"), ("$", "dollars"), ("£", "livres"))
    for symbol, word in table:
        if symbol in text:
            subs.append((symbol, word))
            text = text.replace(symbol, " " + word)
    return re.sub(r"\s+", " ", text)


def apply_dictionary(text: str, dictionary: Dict[str, str],
                     subs: List[Tuple[str, str]]) -> str:
    """Termes validés (insensible à la casse pour les acronymes)."""
    for term in sorted(dictionary, key=len, reverse=True):
        spoken = dictionary[term]
        if term.isupper():
            pattern = re.compile(r"\b%s\b" % re.escape(term))
        else:
            pattern = re.compile(r"\b%s\b" % re.escape(term),
                                 re.IGNORECASE)
        def fix(match: re.Match, _s=spoken) -> str:
            subs.append((match.group(0), _s))
            return _s
        text = pattern.sub(fix, text)
    return text


def spell_acronyms(text: str, subs: List[Tuple[str, str]]) -> str:
    """Acronymes MAJUSCULES inconnus épellés (jamais inventés)."""
    def spell(match: re.Match) -> str:
        word = match.group(0)
        spelled = _spell_letters(word)
        subs.append((word, spelled))
        return spelled
    return re.sub(r"\b[A-Z]{2,}\b", spell, text)


def prepare(text: Any,
            dictionary: Any = None) -> PreparedSpeech:
    """Prépare la vocalisation. Sens et affichage préservés."""
    if not isinstance(text, str):
        return PreparedSpeech(display="", spoken="")
    display = text
    subs: List[Tuple[str, str]] = []
    merged: Dict[str, str] = dict(DEFAULT_DICTIONARY)
    if isinstance(dictionary, dict):
        for key, value in dictionary.items():
            if isinstance(key, str) and isinstance(value, str) \
                    and key.strip() and value.strip():
                merged[key.strip()] = value.strip()
    spoken = normalize_dates_times(text, subs)
    spoken = normalize_currency(spoken, subs)
    spoken = normalize_numbers(spoken, subs)
    spoken = apply_dictionary(spoken, merged, subs)
    spoken = spell_acronyms(spoken, subs)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    return PreparedSpeech(display=display, spoken=spoken, substitutions=subs)
