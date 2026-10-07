"""Tests normalisation FR + dictionnaire (rapides, sans moteur)."""

from __future__ import annotations

from core.voice.pronunciation import (
    DEFAULT_DICTIONARY,
    PreparedSpeech,
    int_to_french,
    prepare,
)


def test_nombres_mandat():
    assert prepare("100").spoken == "cent"
    assert prepare("20").spoken == "vingt"
    assert prepare("97").spoken == "quatre-vingt-dix-sept"
    assert prepare("1000").spoken == "mille"
    assert prepare("1500").spoken == "mille cinq cents"
    assert prepare("2026").spoken == "deux mille vingt-six"
    assert prepare("97,45").spoken == \
        "quatre-vingt-dix-sept virgule quarante-cinq"
    assert prepare("2,5 %").spoken == "deux virgule cinq pour cent"
    assert prepare("0,05").spoken == "zéro virgule zéro cinq"


def test_nombres_contextes():
    assert prepare("50097,45").spoken == \
        "cinquante mille quatre-vingt-dix-sept virgule quarante-cinq"
    assert prepare("1 500").spoken == "mille cinq cents"
    assert prepare("1,500").spoken == "mille cinq cents"
    assert prepare("97.45").spoken == \
        "quatre-vingt-dix-sept virgule quarante-cinq"
    assert prepare("3,14159").spoken == \
        "trois virgule un quatre un cinq neuf"
    assert prepare("50%").spoken == "cinquante pour cent"
    assert prepare("100 USDT").spoken == "cent U S D T"


def test_dates_heures():
    assert prepare("07/10/2026").spoken == \
        "sept octobre deux mille vingt-six"
    assert prepare("20h30").spoken == "vingt heures trente"
    assert prepare("20h").spoken == "vingt heures"


def test_acronymes_et_termes():
    assert prepare("TAIOS").spoken == "T A I O S"
    assert "Q A N X O R U S" in prepare("QanXorus").spoken
    assert prepare("Le montant est de 100 USDT.").spoken == \
        "Le montant est de cent U S D T."
    assert prepare("NASA et CNRS").spoken == "N A S A et C N R S"


def test_dictionnaire_extensible():
    assert "TAIOS" in DEFAULT_DICTIONARY
    made = prepare("Ouvrir TAIOS.", {"TAIOS": "tayos"})
    assert made.spoken == "Ouvrir tayos."
    assert made.display == "Ouvrir TAIOS."
    made = prepare("Bonjour.", {"  ": "x", "": "y", 1: 2})
    assert made.spoken == "Bonjour."


def test_affichage_preserve_et_trace():
    made = prepare("Le montant est de 100 USDT.")
    assert isinstance(made, PreparedSpeech)
    assert made.display == "Le montant est de 100 USDT."
    assert ("100", "cent") in made.substitutions
    assert prepare("").spoken == ""
    assert prepare(None).spoken == ""


def test_int_to_french_bornes():
    assert int_to_french(0) == "zéro"
    assert int_to_french(71) == "soixante-et-onze"
    assert int_to_french(80) == "quatre-vingts"
    assert int_to_french(81) == "quatre-vingt-un"
    assert int_to_french(200) == "deux cents"
    assert int_to_french(203) == "deux cent trois"
    assert int_to_french(1000000) == "un million"
    try:
        int_to_french(-1)
        raise AssertionError("borne basse")
    except ValueError:
        pass
    try:
        int_to_french(10 ** 10)
        raise AssertionError("borne haute")
    except ValueError:
        pass
