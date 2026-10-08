"""Wilfrid — présence visuelle (rendu terminal réel, sans autorité).

Deux sorties : `render_json` (toujours) et `render_ansi` (art terminal
déterministe : même frame + même tick = même image). Aucun toolkit
graphique, stdlib seule. Sans TTY, seul le JSON est pertinent
(repli honnête, pas de pixels simulés). Le rendu ne bloque jamais le
runtime : pur, borné, sans E/S.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from core.visual.states import VisualFrame

_EYES = {
    "detendus": ("◠", "◠"),
    "ouverts-attentifs": ("●", "●"),
    "haut-concentre": ("◔", "◔"),
    "vers-utilisateur": ("●", "●"),
    "calmes": ("◡", "◡"),
    "concentres": ("◉", "◉"),
    "grands-ouverts": ("○", "○"),
    "asymetriques": ("●", "◠"),
    "surpris": ("○", "○"),
    "mi-clos": ("◡", "◡"),
    "tombants": ("◡", "◡"),
    "fermes": ("─", "─"),
    "en-x-ludique": ("×", "×"),
}

_MOUTHS = {
    "neutre": "─",
    "leger-sourire": "◡",
    "fermee": "─",
    "parole": "○",
    "sourire": "◡",
    "hesitante": "~",
    "surprise": "○",
    "triste": "◠",
}

_RINGS = ("lent·.oOo.·", "réactif≈≈≈≈≈", "ralenti·.o.·",
          "animé.oOoOo.", "pulsation♥♥♥", "dynamique≡≡≡≡≡",
          "désync≈.×.≈", "instable∼∼∼")


def _ring_line(vitesse: str, tick: int) -> str:
    index = abs(hash(vitesse)) % len(_RINGS)
    motif = _RINGS[index]
    shift = tick % max(len(motif), 1)
    return motif[shift:] + motif[:shift]


def render_ansi(frame: Any, tick: int = 0) -> str:
    """Image terminal déterministe de la présence (9 lignes)."""
    if not isinstance(frame, VisualFrame):
        return ""
    gauche, droite = _EYES.get(frame.yeux.expression, ("●", "●"))
    bouche = _MOUTHS.get(frame.bouche.expression, "─")
    if frame.bouche.parole_active and (tick // 2) % 2:
        bouche = "◯"
    halo = "░" if frame.noyau.luminosite < 0.5 else "▒"
    if frame.noyau.luminosite >= 0.8:
        halo = "▓"
    lignes = [
        "   . - ~ %s ~ - .   " % frame.etat,
        "     %s  %s  %s     " % (halo, halo, halo),
        "   %s   %s   %s   %s   " % (halo, gauche, droite, halo),
        "  %s    \\%s/    %s  " % (halo, bouche, halo),
        "   %s  \\___/  %s   " % (halo, halo),
        "     %s  %s  %s     " % (halo, halo, halo),
        "%s" % _ring_line(frame.noyau.anneaux_vitesse, tick),
    ]
    if frame.mode:
        lignes.append("  :: %s ::  " % frame.mode)
    lignes.append("Wilfrid ◉ %s" % frame.etat)
    return "\n".join(lignes)


def render_json(frame: Any) -> str:
    """Trame structurée (repli sans terminal)."""
    if not isinstance(frame, VisualFrame):
        return "{}"
    return json.dumps({
        "etat": frame.etat, "mode": frame.mode,
        "yeux": {"expression": frame.yeux.expression,
                 "regard": frame.yeux.regard,
                 "taille": frame.yeux.taille,
                 "clignement": frame.yeux.clignement,
                 "asymetrie": frame.yeux.asymetrie},
        "bouche": {"expression": frame.bouche.expression,
                   "parole_active": frame.bouche.parole_active},
        "noyau": {"luminosite": frame.noyau.luminosite,
                  "anneaux_vitesse": frame.noyau.anneaux_vitesse,
                  "synchronises": frame.noyau.anneaux_synchronises,
                  "balayage": frame.noyau.balayage,
                  "expansion": frame.noyau.expansion},
        "environnement": frame.environnement,
        "raison": frame.raison,
    }, ensure_ascii=False)


def describe() -> Dict[str, Any]:
    """Capacités de rendu (sans effet)."""
    return {"sorties": ["ansi-terminal", "json"],
            "graphique-pixel": False,
            "network": False, "authority": False}
