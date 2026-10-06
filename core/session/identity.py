"""Wilfrid — identité technique (P4). Paramètres, pas de raisonnement.

« Monsieur K » est l'identité d'interaction configurée de l'utilisateur :
ni mémoire, ni biométrie, ni identification externe.
"""

from __future__ import annotations

from dataclasses import dataclass

# Provenance : wilfrid_voice.py (VOICE_ID, MODEL_ID) — recopiés ici pour
# éviter toute dépendance du périmètre session vers le moteur vocal.
VOICE_ID = "bIHbv24MWmeRgasZH58o"
TTS_MODEL_ID = "eleven_multilingual_v2"

WILFRID_NAME = "Wilfrid"
WILFRID_INTERNAL_ID = "wilfrid-core"
WILFRID_VERSION = "0.4.0"
WAKE_PHRASE = "Wilfrid"
DEFAULT_USER_NAME = "Monsieur K"
ACTIVATION_RESPONSE = "Oui, Monsieur K. Je suis là."


@dataclass(frozen=True)
class WilfridIdentity:
    """Identité technique de Wilfrid + identité d'interaction configurée."""

    name: str = WILFRID_NAME
    internal_id: str = WILFRID_INTERNAL_ID
    version: str = WILFRID_VERSION
    wake_phrase: str = WAKE_PHRASE
    user_name: str = DEFAULT_USER_NAME
    voice_id: str = VOICE_ID
    tts_model_id: str = TTS_MODEL_ID

    def activation_response(self) -> str:
        """Texte d'accusé d'activation (donnée future, aucun TTS ici)."""
        return f"Oui, {self.user_name}. Je suis là."
