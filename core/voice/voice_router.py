"""Wilfrid — routeur vocal hybride (connecté/local, sans autorité).

`parole_validée → préparation → provider → audio`. Entrée = texte DÉJÀ
validé par LiveSession/Core uniquement. Sélection déterministe :
config `connected`/`local`/`auto` ; en `auto`, ElevenLabs si configuré,
repli local immédiat à la première erreur (zéro boucle, une tentative).
Aucune sonde réseau proactive : le repli est piloté par l'échec réel ou
par le drapeau `offline_forced`. Aucun import du Core, aucun secret lu
ici (variables lues par `welcome.py`, jamais journalisées).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

ELEVENLABS_TIMEOUT_S = 15.0


@dataclass(frozen=True)
class VoiceReport:
    """Issue du routage : provider + repli, jamais une autorisation."""

    provider: str = "local"
    offline: bool = True
    fallback: bool = False
    reason: str = ""
    spoken_text: str = ""


@dataclass
class VoiceConfig:
    """Configuration persistée hors dépôt (voix officielle gelée ici)."""

    mode: str = "auto"
    offline_voice: str = "upmc-pierre"
    offline_sid: int = 1
    connected_voice_id: Optional[str] = None
    dictionary: Dict[str, str] = field(default_factory=dict)

    def sanitized(self) -> Dict[str, Any]:
        return {"mode": self.mode, "offline_voice": self.offline_voice,
                "offline_sid": self.offline_sid,
                "connected_voice_id_set": bool(self.connected_voice_id),
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
    mode = data.get("mode", "auto")
    if mode not in ("auto", "connected", "local"):
        mode = "auto"
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
                       connected_voice_id=None, dictionary=clean)


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


def elevenlabs_available() -> Tuple[bool, str]:
    """Disponibilité SANS appel réseau : config + paquet présents."""
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    vid = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
    if not key:
        return False, "cle-absente"
    if not vid:
        return False, "voice-id-absent"
    try:
        import elevenlabs  # noqa: F401
    except Exception:
        return False, "paquet-absent"
    return True, ""


def elevenlabs_speak(text: str, *, timeout_s: float = ELEVENLABS_TIMEOUT_S,
                     convert_fn: Any = None) -> Tuple[bool, bytes, str]:
    """Synthèse connectée. `(ok, wav, raison)` ; échec = repli, jamais boucle."""
    if not isinstance(text, str) or not text.strip() \
            or len(text.strip()) > 2000:
        return False, b"", "entree-invalide"
    if convert_fn is not None:
        if not callable(convert_fn):
            return False, b"", "adaptateur-invalide"
        try:
            audio = convert_fn(text.strip())
        except Exception:
            return False, b"", "erreur-connectee"
        if not isinstance(audio, (bytes, bytearray)) or not bytes(audio):
            return False, b"", "audio-invalide"
        return True, bytes(audio), "connecte-injecte"
    from core.voice.welcome import elevenlabs_env_config
    vid, model_id, output_format, _rate = elevenlabs_env_config()
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not vid or not api_key:
        return False, b"", "config-absente"
    try:
        from elevenlabs.client import ElevenLabs
    except Exception:
        return False, b"", "paquet-absent"
    try:
        import concurrent.futures as futures
        client = ElevenLabs(api_key=api_key)

        def convert() -> bytes:
            return b"".join(client.text_to_speech.convert(
                voice_id=vid, text=text.strip(), model_id=model_id,
                output_format=output_format))

        with futures.ThreadPoolExecutor(max_workers=1) as pool:
            raw = pool.submit(convert).result(timeout=float(timeout_s))
    except Exception:
        return False, b"", "erreur-connectee"
    if not raw:
        return False, b"", "audio-invalide"
    return True, bytes(raw), "connecte"


def speak_validated(text: Any, *, config: Any = None,
                    offline_forced: bool = False,
                    convert_fn: Any = None,
                    dictionary: Any = None) -> Tuple[str, bytes, VoiceReport]:
    """Vocalise un texte validé. `(statut, audio, rapport)` honnêtes."""
    from core.voice.pronunciation import prepare
    from core.voice.tts_local import VoiceProfile, synth_fn_for
    cfg = config if isinstance(config, VoiceConfig) else VoiceConfig()
    if not isinstance(text, str) or not text.strip():
        return "SKIPPED", b"", VoiceReport(
            provider="aucun", offline=bool(offline_forced),
            fallback=False, reason="texte-vide", spoken_text="")
    if len(text.strip()) > 2000:
        return "FAILED", b"", VoiceReport(
            provider="aucun", offline=bool(offline_forced),
            fallback=False, reason="borne-depassee", spoken_text="")
    merged_dict: Dict[str, str] = dict(cfg.dictionary)
    if isinstance(dictionary, dict):
        for key, value in dictionary.items():
            if isinstance(key, str) and isinstance(value, str) \
                    and key.strip() and value.strip():
                merged_dict[key.strip()] = value.strip()
    prepared = prepare(text.strip(), merged_dict)
    use_connected = (not offline_forced) and cfg.mode in ("auto",
                                                          "connected")
    if use_connected:
        available, _why = elevenlabs_available()
        if available or convert_fn is not None:
            ok, audio, reason = elevenlabs_speak(
                prepared.spoken, convert_fn=convert_fn)
            if ok:
                return "OK", audio, VoiceReport(
                    provider="elevenlabs", offline=False, fallback=False,
                    reason=reason, spoken_text=prepared.spoken)
            if cfg.mode == "connected":
                return "FAILED", b"", VoiceReport(
                    provider="elevenlabs", offline=False, fallback=False,
                    reason=reason, spoken_text=prepared.spoken)
    profile = VoiceProfile(voice=cfg.offline_voice, sid=cfg.offline_sid)
    try:
        audio = synth_fn_for(profile)(prepared.spoken)
    except Exception as exc:
        return "FAILED", b"", VoiceReport(
            provider="local", offline=True,
            fallback=use_connected, reason=str(exc)[:80],
            spoken_text=prepared.spoken)
    return "OK", audio, VoiceReport(
        provider="local", offline=True, fallback=use_connected,
        reason="local-ok", spoken_text=prepared.spoken)


def describe() -> Dict[str, Any]:
    """État du routeur (sans effet)."""
    available, reason = elevenlabs_available()
    return {"providers": ["elevenlabs", "local"],
            "elevenlabs_configured": available,
            "elevenlabs_reason": reason,
            "official_offline_voice": "upmc-pierre",
            "network": False, "authority": False}
