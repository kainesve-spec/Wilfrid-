"""Wilfrid — capacités Android contrôlées (déclaratif, sans autorité).

Distinction centrale : DISPONIBLE (technique) ≠ ACCORDÉ (Wilfrid) ≠
AUTORISÉ (cette action) ≠ RÉUSSI (effet vérifié). Registre statique,
DEFAULT DENY : toute capacité absente ou non accordée est refusée.
Données personnelles : jamais lues sans autorisation explicite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

STATES = ("AVAILABLE", "AVAILABLE_WITH_PERMISSION",
          "AVAILABLE_WITH_COMPONENT", "NOT_TESTED", "UNAVAILABLE")

RISKS = ("faible", "modere", "sensible", "critique")

SENSITIVE_IDS = ("SMS_SEND", "TELEPHONY_CALL", "SAF_DELETE",
                 "NOTIFICATION_REMOVE", "OPEN_URL", "OPEN_APP",
                 "SHARE_EXTERNAL")


@dataclass(frozen=True)
class Capability:
    """Fiche capacité : mécanisme, risque, vérification, restrictions."""

    id: str = ""
    description: str = ""
    categorie: str = ""
    mecanisme: str = ""
    commande: str = ""
    etat: str = "NOT_TESTED"
    risque: str = "modere"
    reversible: bool = True
    permission_android: str = ""
    confirmation_requise: bool = False
    verification: str = ""
    provenance: str = "audit-chantier-1"
    restrictions: str = ""


def _definition() -> Tuple[Capability, ...]:
    return (
        Capability(
            id="BATTERY_STATUS", description="État batterie (lecture)",
            categorie="systeme", mecanisme="termux-api",
            commande="termux-battery-status", etat="AVAILABLE",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="champs percentage/status présents",
            restrictions="lecture seule"),
        Capability(
            id="AUDIO_INFO", description="Paramètres audio (lecture)",
            categorie="systeme", mecanisme="termux-api",
            commande="termux-audio-info", etat="AVAILABLE",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="sample-rate présent",
            restrictions="lecture seule"),
        Capability(
            id="CAMERA_LIST", description="Caméras disponibles (liste)",
            categorie="materiel", mecanisme="termux-api",
            commande="termux-camera-info", etat="AVAILABLE",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="liste non vide avec id",
            restrictions="liste uniquement, aucune capture"),
        Capability(
            id="SENSOR_LIST", description="Capteurs disponibles (liste)",
            categorie="materiel", mecanisme="termux-api",
            commande="termux-sensor -l", etat="AVAILABLE",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="liste non vide",
            restrictions="liste uniquement, aucune lecture continue"),
        Capability(
            id="TTS_ENGINES", description="Moteurs TTS (liste)",
            categorie="systeme", mecanisme="termux-api",
            commande="termux-tts-engines", etat="AVAILABLE",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="liste non vide",
            restrictions="liste uniquement, aucune synthèse"),
        Capability(
            id="SYSTEM_INFO",
            description="Informations système non personnelles",
            categorie="systeme", mecanisme="termux-api",
            commande="termux-info", etat="AVAILABLE_WITH_COMPONENT",
            risque="faible", reversible=True, permission_android="",
            confirmation_requise=False,
            verification="sortie non vide",
            restrictions="lecture seule, sans diffusion"),
        Capability(
            id="STORAGE_READ",
            description="Lecture fichier déjà autorisé (SAF/scope)",
            categorie="fichiers", mecanisme="termux-api/saf",
            commande="termux-saf-read", etat="AVAILABLE_WITH_PERMISSION",
            risque="modere", reversible=True,
            permission_android=" SAF/storage accordé",
            confirmation_requise=True,
            verification="octets lus conformes",
            restrictions="chemins explicites uniquement"),
        Capability(
            id="OPEN_URL", description="Ouverture d'URL via intent",
            categorie="applications", mecanisme="intent",
            commande="termux-open-url", etat="AVAILABLE_WITH_COMPONENT",
            risque="modere", reversible=True, permission_android="",
            confirmation_requise=True,
            verification="intent accepté (pas de succès distant)",
            restrictions="URL explicite, engagement externe possible"),
        Capability(
            id="OPEN_APP", description="Lancement d'application via intent",
            categorie="applications", mecanisme="intent",
            commande="termux-open", etat="AVAILABLE_WITH_COMPONENT",
            risque="modere", reversible=True, permission_android="",
            confirmation_requise=True,
            verification="intent accepté (pas d'automatisation interne)",
            restrictions="lancement seul, aucune manipulation interne"),
        Capability(
            id="CONTACT_LIST", description="Contacts (lecture)",
            categorie="personnel", mecanisme="termux-api",
            commande="termux-contact-list",
            etat="AVAILABLE_WITH_PERMISSION", risque="sensible",
            reversible=True, permission_android="READ_CONTACTS",
            confirmation_requise=True,
            verification="structure liste",
            restrictions="jamais sans autorisation explicite"),
        Capability(
            id="LOCATION", description="Localisation (lecture)",
            categorie="personnel", mecanisme="termux-api",
            commande="termux-location", etat="AVAILABLE_WITH_PERMISSION",
            risque="sensible", reversible=True,
            permission_android="ACCESS_FINE_LOCATION",
            confirmation_requise=True,
            verification="coordonnées présentes",
            restrictions="jamais sans autorisation explicite"),
        Capability(
            id="SMS_SEND", description="Envoi SMS",
            categorie="communications", mecanisme="termux-api",
            commande="termux-sms-send", etat="AVAILABLE_WITH_PERMISSION",
            risque="critique", reversible=False,
            permission_android="SEND_SMS", confirmation_requise=True,
            verification="effet réel ou UNKNOWN explicite",
            restrictions="engagement externe, jamais implicite"),
        Capability(
            id="TELEPHONY_CALL", description="Appel téléphonique",
            categorie="communications", mecanisme="termux-api",
            commande="termux-telephony-call",
            etat="AVAILABLE_WITH_PERMISSION", risque="critique",
            reversible=False, permission_android="CALL_PHONE",
            confirmation_requise=True,
            verification="effet réel ou UNKNOWN explicite",
            restrictions="engagement externe, jamais implicite"),
        Capability(
            id="SAF_DELETE", description="Suppression fichier (SAF)",
            categorie="fichiers", mecanisme="termux-api/saf",
            commande="termux-saf-rm", etat="AVAILABLE_WITH_PERMISSION",
            risque="critique", reversible=False, permission_android="",
            confirmation_requise=True,
            verification="absence vérifiée du fichier",
            restrictions="irréversible, jamais implicite"),
        Capability(
            id="SHARE_EXTERNAL", description="Partage vers application",
            categorie="applications", mecanisme="intent",
            commande="termux-share", etat="AVAILABLE_WITH_COMPONENT",
            risque="sensible", reversible=False, permission_android="",
            confirmation_requise=True,
            verification="intent accepté (pas de succès distant)",
            restrictions="engagement externe, jamais implicite"),
        Capability(
            id="NOTIFICATION_REMOVE", description="Retrait notification",
            categorie="systeme", mecanisme="termux-api",
            commande="termux-notification-remove",
            etat="AVAILABLE_WITH_COMPONENT", risque="modere",
            reversible=False, permission_android="",
            confirmation_requise=True,
            verification="retrait confirmé ou UNKNOWN",
            restrictions="ne jamais masquer une alerte critique"),
    )


@dataclass
class AndroidRegistry:
    """Registre fermé + accords explicites (défaut : refus)."""

    grants: Tuple[Tuple[str, str], ...] = ()

    def _table(self) -> Dict[str, Capability]:
        return {cap.id: cap for cap in _definition()}

    def list(self) -> Tuple[Capability, ...]:
        """Inventaire déterministe (ordre stable)."""
        table = self._table()
        return tuple(table[key] for key in sorted(table))

    def get(self, capability_id: Any) -> Any:
        """Fiche exacte, `None` si inconnue."""
        if not isinstance(capability_id, str):
            return None
        return self._table().get(capability_id)

    def exists(self, capability_id: Any) -> bool:
        """Présence stricte."""
        return self.get(capability_id) is not None

    def granted(self, capability_id: str) -> bool:
        """Accord Wilfrid actuel (défaut : refus)."""
        grants = dict(self.grants) if isinstance(self.grants, tuple) \
            else {}
        return bool(grants.get(capability_id, False))

    def grant(self, capability_id: str,
              decided_by: Any) -> Tuple[bool, "AndroidRegistry"]:
        """Accorde explicitement (traçable par `decided_by`)."""
        if not self.exists(capability_id) or not isinstance(decided_by,
                                                             str) \
                or not decided_by.strip():
            return False, self
        grants = dict(self.grants)
        grants[capability_id] = "accorde-par:" + decided_by.strip()[:64]
        return True, AndroidRegistry(
            grants=tuple(sorted(grants.items())))

    def revoke(self, capability_id: str) -> Tuple[bool, "AndroidRegistry"]:
        """Révoque immédiatement (effet instantané)."""
        grants = dict(self.grants) if isinstance(self.grants, tuple) \
            else {}
        if capability_id not in grants:
            return False, self
        del grants[capability_id]
        return True, AndroidRegistry(
            grants=tuple(sorted(grants.items())))


DEFAULT_GRANTED = ("BATTERY_STATUS", "AUDIO_INFO", "CAMERA_LIST",
                   "SENSOR_LIST", "TTS_ENGINES", "SYSTEM_INFO")


def default_registry() -> AndroidRegistry:
    """Registre avec accords inoffensifs par défaut (documentés)."""
    grants = tuple(sorted((cap_id, "defaut-inoffensif")
                          for cap_id in DEFAULT_GRANTED))
    return AndroidRegistry(grants=grants)


def describe() -> Dict[str, Any]:
    """Inventaire déclaratif (sans effet)."""
    return {"capacites": [cap.id for cap in default_registry().list()],
            "statique": True, "default_deny": True,
            "accordees_defaut": list(DEFAULT_GRANTED),
            "network": False, "authority": False}
