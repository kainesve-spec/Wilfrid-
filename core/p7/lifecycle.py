"""Wilfrid — lifecycle P7 C1 (transitions fermées, pures, sans effet).

Terminaux : REFUSÉ / RETIRÉ (par version). Aucune transition automatique.
L'expiration est un constat, jamais une autorisation.
"""

from __future__ import annotations

from typing import Tuple

from core.p7 import errors as E

SKILL_STATES = (
    "PROPOSÉ", "DÉCLARÉ", "VÉRIFIÉ", "APPROUVÉ", "REFUSÉ",
    "ACTIF", "SUSPENDU", "RETIRÉ",
)

PLUGIN_STATES = (
    "RÉCEPTIONNÉ", "MANIFESTE_VÉRIFIÉ", "INTÉGRITÉ_VÉRIFIÉE", "APPROUVÉ",
    "REFUSÉ", "INSTALLÉ", "ACTIVÉ", "SUSPENDU", "RÉVOQUÉ", "RETIRÉ",
)

CAPABILITY_STATES = (
    "DEMANDÉE", "CONTRÔLÉE", "ACCORDÉE", "REFUSÉE", "ACTIVE",
    "RÉDUITE", "AUGMENTÉE", "EXPIRÉE", "RÉVOQUÉE", "CLÔTURÉE",
)

TOOL_STATES = (
    "DÉCLARÉ", "CLASSÉ", "VÉRIFIÉ", "HOMOLOGUÉ", "REFUSÉ",
    "INVOCABLE", "GELÉ", "RETIRÉ",
)

TERMINAL = ("REFUSÉ", "REFUSÉE", "RÉVOQUÉ", "RÉVOQUÉE", "RETIRÉ", "EXPIRÉE", "CLÔTURÉE")

_TRANSITIONS = {
    "PROPOSÉ": ("DÉCLARÉ",),
    "DÉCLARÉ": ("VÉRIFIÉ", "REFUSÉ"),
    "VÉRIFIÉ": ("APPROUVÉ", "REFUSÉ"),
    "APPROUVÉ": ("ACTIF", "REFUSÉ"),
    "ACTIF": ("SUSPENDU", "RETIRÉ"),
    "SUSPENDU": ("ACTIF", "RETIRÉ"),
    "REFUSÉ": (),
    "RETIRÉ": (),
    "RÉCEPTIONNÉ": ("MANIFESTE_VÉRIFIÉ", "REFUSÉ"),
    "MANIFESTE_VÉRIFIÉ": ("INTÉGRITÉ_VÉRIFIÉE", "REFUSÉ"),
    "INTÉGRITÉ_VÉRIFIÉE": ("APPROUVÉ", "REFUSÉ"),
    "INSTALLÉ": ("ACTIVÉ", "RETIRÉ"),
    "ACTIVÉ": ("SUSPENDU", "RÉVOQUÉ"),
    "SUSPENDU": ("ACTIVÉ", "RÉVOQUÉ"),
    "RÉVOQUÉ": ("RETIRÉ",),
    "DEMANDÉE": ("CONTRÔLÉE", "REFUSÉE"),
    "CONTRÔLÉE": ("ACCORDÉE", "REFUSÉE"),
    "ACCORDÉE": ("ACTIVE", "REFUSÉE"),
    "ACTIVE": ("RÉDUITE", "AUGMENTÉE", "EXPIRÉE", "RÉVOQUÉE"),
    "RÉDUITE": ("ACTIVE", "EXPIRÉE", "RÉVOQUÉE"),
    "AUGMENTÉE": ("ACTIVE", "EXPIRÉE", "RÉVOQUÉE"),
    "EXPIRÉE": ("CLÔTURÉE",),
    "RÉVOQUÉE": ("CLÔTURÉE",),
    "REFUSÉE": (),
    "CLÔTURÉE": (),
    "DÉCLARÉ": ("CLASSÉ", "REFUSÉ"),
    "CLASSÉ": ("VÉRIFIÉ", "REFUSÉ"),
    "VÉRIFIÉ": ("HOMOLOGUÉ", "REFUSÉ"),
    "HOMOLOGUÉ": ("INVOCABLE", "REFUSÉ"),
    "INVOCABLE": ("GELÉ", "RETIRÉ"),
    "GELÉ": ("INVOCABLE", "RETIRÉ"),
}


def is_valid_transition(current: str, target: str) -> Tuple[bool, str]:
    """Valide une transition ; terminale = aucun départ ; inconnue = DENY."""
    if not isinstance(current, str) or not isinstance(target, str):
        return False, E.LIFECYCLE_INVALID
    allowed = _TRANSITIONS.get(current)
    if allowed is None:
        return False, E.LIFECYCLE_INVALID
    if target not in allowed:
        return False, E.LIFECYCLE_INVALID
    return True, "ok"
