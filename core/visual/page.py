"""Wilfrid — page locale (état honnête, sans autorité).

HTML auto-rafraîchie (2 s) : image PNG, état textuel, horodatage,
fraîcheur/périmé explicites. Aucune commande métier, aucun bouton
d'autorisation, aucun secret, aucune donnée personnelle. Si le
snapshot est trop vieux : signalé PÉRIMÉ, jamais inventé.
"""

from __future__ import annotations

import time
from typing import Any, Dict

STALE_AFTER_S = 30.0
REFRESH_S = 2


def page_html(snapshot: Any, png_path: str = "/png",
              now: Any = None) -> str:
    """Construit la page depuis un snapshot (données seules)."""
    moment = float(now) if isinstance(now, (int, float)) else time.time()
    data = snapshot if isinstance(snapshot, dict) else {}
    etat = str(data.get("etat", "INCONNU"))
    instant = data.get("horodatage", 0.0)
    try:
        age = max(0.0, moment - float(instant))
    except (TypeError, ValueError):
        age = -1.0
    if age < 0:
        fraicheur = "HORODATAGE INVALIDE"
    elif age <= STALE_AFTER_S:
        fraicheur = "à jour (%ds)" % int(age)
    else:
        fraicheur = "PÉRIMÉ (%ds > %ds)" % (int(age), int(STALE_AFTER_S))
    raison = str(data.get("raison", ""))
    lignes = [
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">",
        "<meta http-equiv=\"refresh\" content=\"%d\">" % REFRESH_S,
        "<title>Wilfrid — présence locale</title></head><body>",
        "<h1>Wilfrid : %s</h1>" % _escape(etat),
        "<p>Fraîcheur : %s</p>" % _escape(fraicheur),
        "<p>Instantané : %s</p>" % _escape(str(instant)),
    ]
    if raison:
        lignes.append("<p>Détail : %s</p>" % _escape(raison[:200]))
    lignes.append("<img src=\"%s\" alt=\"Wilfrid %s\" width=\"256\">"
                  % (png_path, _escape(etat)))
    lignes.append("<p>Lecture seule : aucun bouton d'action ici.</p>")
    lignes.append("</body></html>")
    return "\n".join(lignes)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;") \
        .replace(">", "&gt;").replace('"', "&quot;")


def describe() -> Dict[str, Any]:
    """Contrat page (sans effet)."""
    return {"rafraichissement_s": REFRESH_S,
            "perime_apres_s": STALE_AFTER_S,
            "commandes": 0, "secrets": 0,
            "network": False, "authority": False}
