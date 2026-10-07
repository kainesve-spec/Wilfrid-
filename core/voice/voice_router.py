"""Wilfrid — voix unique locale Pierre (sans autorité).

Décision utilisateur gelée : UNE SEULE voix, Pierre (upmc, sid=1),
connecté ou non. `parole_validée → préparation → Pierre → audio`.
Entrée = texte DÉJÀ validé par LiveSession/Core uniquement. Aucun appel
réseau : aucun provider distant dans ce pipeline (fichiers historiques
conservés intacts hors pipeline). Aucun import du Core, aucun secret
lu ici.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class VoiceReport:
    """Issue vocale : provider + état, jamais une autorisation."""

    provider: str = "local"
    offline: bool = True
    fallback: bool = False
    reason: str = ""
    spoken_text: str = ""


@dataclass
class VoiceConfig:
    """Configuration persistée hors dépôt (voix officielle gelée ici)."""

    mode: str = "local"
    offline_voice: str = "upmc-pierre"
    offline_sid: int = 1
    dictionary: Dict[str, str] = field(default_factory=dict)

    def sanitized(self) -> Dict[str, Any]:
        return {"mode": self.mode, "offline_voice": self.offline_voice,
                "offline_sid": self.offline_sid,
                "dictionary_terms": sorted(self.dictionary)}


def config_path() -> str:
    return str(Path.home() / ".local" / "share" / "wilfrid" /
               "voice_config.json")


def load_config(path: Any = None) -> VoiceConfig:
    """Charge la configuration, défauts sûrs si absente/invalide."""
    fallback = VoiceConfig()
    target = str(path) if path else config_path()
    try:
        raw = Path(target).read_text(encoding="utf-8")
    except OSError:
        return fallback
    try:
        data = json.loads(raw)
    except ValueError:
        return fallback
    if not isinstance(data, dict):
        return fallback
    mode = data.get("mode", "local")
    if mode != "local":
        mode = "local"
    dictionary = data.get("dictionary", {})
    if not isinstance(dictionary, dict):
        dictionary = {}
    clean = {str(k): str(v) for k, v in dictionary.items()
             if isinstance(k, str) and isinstance(v, str)
             and k.strip() and v.strip()}
    try:
        sid = int(data.get("offline_sid", 1))
    except (TypeError, ValueError):
        sid = 1
    voice = data.get("offline_voice", "upmc-pierre")
    if not isinstance(voice, str) or not voice.strip():
        voice = "upmc-pierre"
    return VoiceConfig(mode=mode, offline_voice=voice.strip(), offline_sid=sid,
                       dictionary=clean)


def save_config(config: VoiceConfig, path: Any = None) -> Tuple[bool, str]:
    """Persiste la configuration (jamais de secret dedans)."""
    if not isinstance(config, VoiceConfig):
        return False, "entree-invalide"
    target = Path(str(path)) if path else Path(config_path())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"mode": config.mode,
                   "offline_voice": config.offline_voice,
                   "offline_sid": config.offline_sid,
                   "dictionary": config.dictionary}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    except OSError:
        return False, "erreur-ecriture"
    return True, "ok"


def speak_validated(text: Any, *, config: Any = None,
                    synth_fn: Any = None,
                    dictionary: Any = None) -> Tuple[str, bytes, VoiceReport]:
    """Vocalise un texte validé avec Pierre. `(statut, audio, rapport)`."""
    from core.voice.pronunciation import prepare
    from core.voice.tts_local import VoiceProfile, synth_fn_for
    cfg = config if isinstance(config, VoiceConfig) else VoiceConfig()
    if not isinstance(text, str) or not text.strip():
        return "SKIPPED", b"", VoiceReport(
            provider="aucun", offline=True,
            fallback=False, reason="texte-vide", spoken_text="")
    if len(text.strip()) > 2000:
        return "FAILED", b"", VoiceReport(
            provider="aucun", offline=True,
            fallback=False, reason="borne-depassee", spoken_text="")
    merged_dict: Dict[str, str] = dict(cfg.dictionary)
    if isinstance(dictionary, dict):
        for key, value in dictionary.items():
            if isinstance(key, str) and isinstance(value, str) \
                    and key.strip() and value.strip():
                merged_dict[key.strip()] = value.strip()
    prepared = prepare(text.strip(), merged_dict)
    if synth_fn is not None and not callable(synth_fn):
        return "FAILED", b"", VoiceReport(
            provider="local", offline=True, fallback=False,
            reason="adaptateur-invalide", spoken_text=prepared.spoken)
    profile = VoiceProfile(voice=cfg.offline_voice, sid=cfg.offline_sid)
    make = synth_fn if callable(synth_fn) else synth_fn_for(profile)
    try:
        audio = make(prepared.spoken)
    except Exception as exc:
        return "FAILED", b"", VoiceReport(
            provider="local", offline=True, fallback=False,
            reason=str(exc)[:80], spoken_text=prepared.spoken)
    if not isinstance(audio, (bytes, bytearray)) or not bytes(audio):
        return "FAILED", b"", VoiceReport(
            provider="local", offline=True, fallback=False,
            reason="audio-invalide", spoken_text=prepared.spoken)
    return "OK", bytes(audio), VoiceReport(
        provider="local", offline=True, fallback=False,
        reason="local-ok", spoken_text=prepared.spoken)


def describe() -> Dict[str, Any]:
    """État de la voix (sans effet)."""
    return {"providers": ["local"],
            "official_voice": "upmc-pierre",
            "network": False, "authority": False}
