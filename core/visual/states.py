"""Wilfrid — grammaire visuelle (données seules, sans autorité).

États fondamentaux, modes contextuels/humoristiques, priorité visuelle
(§10), spécifications yeux/bouche/noyau/anneaux. La couche visuelle
REPRÉSENTE l'état réel du moteur : SUCCESS exige une vérification
réussie explicite, WAITING_APPROVAL n'autorise jamais. Données pures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

FUNDAMENTAL = ("IDLE", "LISTENING", "THINKING", "SPEAKING",
               "WAITING_APPROVAL", "EXECUTING", "VERIFYING", "SUCCESS",
               "UNCERTAIN", "ERROR", "INTERRUPTED", "OFFLINE")

MODES = ("TRANSLATION", "PRODUCTIVITY", "DATA_ANALYSIS", "SECURITY",
         "SECRET", "PARANORMAL", "CHEF", "PHILOSOPHER", "COFFEE",
         "DISBELIEF", "SAD", "MELTDOWN", "SUCCESS_CELEBRATION", "SLEEP",
         "SPACE")

HUMOROUS = ("SECRET", "PARANORMAL", "CHEF", "PHILOSOPHER", "COFFEE",
            "DISBELIEF", "SAD", "MELTDOWN", "SUCCESS_CELEBRATION",
            "SLEEP", "SPACE")

PRIORITY = ("ERROR", "OFFLINE", "INTERRUPTED", "WAITING_APPROVAL",
            "EXECUTING", "VERIFYING", "SUCCESS", "UNCERTAIN", "SPEAKING",
            "LISTENING", "THINKING", "MODE", "IDLE")

EYES = ("detendus", "ouverts-attentifs", "haut-concentre", "vers-utilisateur",
        "calmes", "concentres", "grands-ouverts", "asymetriques",
        "surpris", "mi-clos", "tombants", "fermes", "en-x-ludique")

MOUTHS = ("neutre", "leger-sourire", "fermee", "parole", "sourire",
          "hesitante", "surprise", "triste")


@dataclass(frozen=True)
class EyeSpec:
    """Yeux : expression gouvernant la personnalité."""

    expression: str = "detendus"
    regard: str = "neutre"
    taille: str = "normale"
    clignement: bool = True
    asymetrie: bool = False


@dataclass(frozen=True)
class MouthSpec:
    """Bouche : parole et expressions contenues."""

    expression: str = "neutre"
    parole_active: bool = False


@dataclass(frozen=True)
class CoreSpec:
    """Noyau et anneaux : intensité et dynamique."""

    luminosite: float = 0.4
    anneaux_vitesse: str = "lents"
    anneaux_synchronises: bool = True
    balayage: bool = False
    expansion: bool = False


@dataclass(frozen=True)
class VisualFrame:
    """Photographie visuelle : état + expressions + contexte, données."""

    etat: str = "IDLE"
    mode: str = ""
    yeux: EyeSpec = field(default_factory=EyeSpec)
    bouche: MouthSpec = field(default_factory=MouthSpec)
    noyau: CoreSpec = field(default_factory=CoreSpec)
    environnement: str = "salon-chaleureux"
    raison: str = ""


_STATE_SPECS: Dict[str, Tuple[EyeSpec, MouthSpec, CoreSpec]] = {
    "IDLE": (EyeSpec("detendus"), MouthSpec("neutre"),
             CoreSpec(0.35, "lents", True, False, False)),
    "LISTENING": (EyeSpec("ouverts-attentifs"), MouthSpec("neutre"),
                  CoreSpec(0.55, "reactifs-audio", True, False, False)),
    "THINKING": (EyeSpec("haut-concentre"), MouthSpec("fermee"),
                 CoreSpec(0.5, "ralentis", True, False, False)),
    "SPEAKING": (EyeSpec("vers-utilisateur"), MouthSpec("parole", True),
                 CoreSpec(0.6, "animes", True, False, False)),
    "WAITING_APPROVAL": (EyeSpec("calmes"), MouthSpec("neutre"),
                         CoreSpec(0.5, "pulsation-lente", True, False,
                                  False)),
    "EXECUTING": (EyeSpec("concentres"), MouthSpec("fermee"),
                  CoreSpec(0.75, "dynamiques", True, False, False)),
    "VERIFYING": (EyeSpec("concentres"), MouthSpec("fermee"),
                  CoreSpec(0.65, "dynamiques", True, True, False)),
    "SUCCESS": (EyeSpec("grands-ouverts"), MouthSpec("sourire"),
                CoreSpec(0.9, "animes", True, False, True)),
    "UNCERTAIN": (EyeSpec("asymetriques", asymetrie=True),
                  MouthSpec("hesitante"), CoreSpec(0.4, "instables", True,
                                                   False, False)),
    "ERROR": (EyeSpec("surpris"), MouthSpec("surprise"),
              CoreSpec(0.55, "desynchronises", False, False, False)),
    "INTERRUPTED": (EyeSpec("detendus"), MouthSpec("neutre"),
                    CoreSpec(0.3, "ralentis", True, False, False)),
    "OFFLINE": (EyeSpec("fermes"), MouthSpec("neutre"),
                CoreSpec(0.1, "lents", True, False, False)),
}


def frame_for(etat: str, *, mode: str = "",
              raison: str = "") -> VisualFrame:
    """Construit la frame d'un état (états inconnus → IDLE honnête)."""
    key = etat if etat in _STATE_SPECS else "IDLE"
    yeux, bouche, noyau = _STATE_SPECS[key]
    clean_mode = mode if mode in MODES else ""
    return VisualFrame(etat=key, mode=clean_mode, yeux=yeux, bouche=bouche,
                       noyau=noyau, raison=str(raison)[:120])


def priority_of(etat: str) -> int:
    """Rang de priorité (§10) : plus petit = plus prioritaire."""
    if etat in PRIORITY:
        return PRIORITY.index(etat)
    return len(PRIORITY)


def pick_state(candidates: Any) -> str:
    """Choisit l'état le plus prioritaire (jamais d'invention)."""
    best = "IDLE"
    if not isinstance(candidates, (tuple, list)):
        return best
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        if candidate == "MODE":
            continue
        if candidate in PRIORITY and priority_of(candidate) < priority_of(
                best):
            best = candidate
    return best


def describe() -> Dict[str, Any]:
    """Grammaire déclarative (sans effet)."""
    return {"fondamentaux": list(FUNDAMENTAL), "modes": list(MODES),
            "priorite": list(PRIORITY), "network": False,
            "authority": False}
