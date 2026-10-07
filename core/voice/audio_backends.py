"""Wilfrid — adaptateurs audio réels locaux (matériel isolé, sans autorité).

Seams remplaçables entre le matériel et `LiveSession`. Aucun import du Core
ici : ce module ne connaît ni sessions, ni gates, ni mandats, ni réseau.
Chaque fonction retourne un état explicite ; aucun succès déclaré sans effet
réel ; aucune boucle non bornée.

Constats d'environnement (honest-by-design) :
- capture PCM réelle : `sounddevice` (OpenSLES Android) si installé ;
- capture conteneur : `termux-microphone-record` ( hors PCM, déclaré tel quel) ;
- sortie vocale : `termux-tts-speak` (TTS système Android) si présent ;
- STT local : aucun moteur distribué pour cet interpréteur/plateforme
  (`vosk` sans distribution compatible ; `whisper` = pile lourde exclue).
  L'absence est un état, jamais une simulation.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

MAX_CAPTURE_SECONDS = 10.0
MAX_CAPTURE_BYTES = 1048576
MIN_SAMPLE_RATE = 8000
MAX_SAMPLE_RATE = 48000
DEFAULT_SAMPLE_RATE = 16000

CAPTURE_STATUSES = ("OK", "FAILED")

CAPTURE_REASONS = (
    "moteur-absent",
    "peripherique-absent",
    "permission-absente",
    "erreur-capture",
    "capture-vide",
    "format-invalide",
    "duree-invalide",
    "borne-depassee",
    "entree-invalide",
)


@dataclass(frozen=True)
class AudioCapture:
    """Résultat de capture : octets + état explicite, jamais une promesse."""

    status: str = "FAILED"
    reason: str = "moteur-absent"
    pcm: bytes = b""
    sample_rate: int = 0
    frames: int = 0
    encoding: str = ""
    backend: str = ""


def _failed(reason: str, backend: str = "") -> AudioCapture:
    if reason not in CAPTURE_REASONS:
        reason = "erreur-capture"
    return AudioCapture(status="FAILED", reason=reason, backend=backend)


def run_capture(capture_fn: Any, *, max_seconds: Any = MAX_CAPTURE_SECONDS,
                max_bytes: Any = MAX_CAPTURE_BYTES,
                sample_rate: Any = DEFAULT_SAMPLE_RATE) -> AudioCapture:
    """Exécute une capture injectée sous bornes strictes, échecs honnêtes."""
    if capture_fn is None or not callable(capture_fn):
        return _failed("moteur-absent", backend="injecte")
    if not isinstance(max_seconds, (int, float)) \
            or isinstance(max_seconds, bool) \
            or not 0.0 < float(max_seconds) <= MAX_CAPTURE_SECONDS:
        return _failed("duree-invalide", backend="injecte")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) \
            or not 0 < max_bytes <= MAX_CAPTURE_BYTES:
        return _failed("borne-depassee", backend="injecte")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) \
            or not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
        return _failed("entree-invalide", backend="injecte")
    try:
        produced = capture_fn(max_seconds=float(max_seconds),
                              sample_rate=int(sample_rate))
    except PermissionError:
        return _failed("permission-absente", backend="injecte")
    except Exception:
        return _failed("erreur-capture", backend="injecte")
    if not isinstance(produced, (tuple, list)) or len(produced) != 2:
        return _failed("format-invalide", backend="injecte")
    pcm, rate = produced
    if not isinstance(pcm, (bytes, bytearray)) or not bytes(pcm):
        return _failed("capture-vide", backend="injecte")
    pcm = bytes(pcm)
    if len(pcm) > int(max_bytes):
        return _failed("borne-depassee", backend="injecte")
    if not isinstance(rate, int) or isinstance(rate, bool) \
            or not MIN_SAMPLE_RATE <= rate <= MAX_SAMPLE_RATE:
        return _failed("format-invalide", backend="injecte")
    frames = len(pcm) // 2
    return AudioCapture(status="OK", reason="", pcm=pcm, sample_rate=rate,
                        frames=frames, encoding="pcm-s16le-mono",
                        backend="injecte")


def sounddevice_pcm_capture(max_seconds: Any = 2.0,
                            sample_rate: Any = DEFAULT_SAMPLE_RATE
                            ) -> AudioCapture:
    """Capture PCM réelle via sounddevice. Absence = état, jamais d'exception."""
    backend = "sounddevice"
    if not isinstance(max_seconds, (int, float)) \
            or isinstance(max_seconds, bool) \
            or not 0.0 < float(max_seconds) <= MAX_CAPTURE_SECONDS:
        return _failed("duree-invalide", backend=backend)
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) \
            or not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
        return _failed("entree-invalide", backend=backend)
    try:
        import sounddevice as sd
    except Exception:
        return _failed("moteur-absent", backend=backend)
    try:
        frames = int(float(max_seconds) * int(sample_rate))
        recording = sd.rec(frames, samplerate=int(sample_rate), channels=1,
                           dtype="int16")
        sd.wait()
    except PermissionError:
        return _failed("permission-absente", backend=backend)
    except Exception as exc:
        message = str(exc).lower()
        if "no device" in message or "device" in message and "default" in message:
            return _failed("peripherique-absent", backend=backend)
        return _failed("erreur-capture", backend=backend)
    try:
        pcm = bytes(recording.tobytes())
    except Exception:
        return _failed("erreur-capture", backend=backend)
    if not pcm:
        return _failed("capture-vide", backend=backend)
    if len(pcm) > MAX_CAPTURE_BYTES:
        return _failed("borne-depassee", backend=backend)
    return AudioCapture(status="OK", reason="", pcm=pcm,
                        sample_rate=int(sample_rate),
                        frames=len(pcm) // 2, encoding="pcm-s16le-mono",
                        backend=backend)


def termux_mic_capture(max_seconds: Any = 2.0,
                       sample_rate: Any = DEFAULT_SAMPLE_RATE,
                       out_dir: Any = None) -> AudioCapture:
    """Capture via `termux-microphone-record`. Conteneur déclaré, pas du PCM."""
    backend = "termux-mic"
    if shutil.which("termux-microphone-record") is None:
        return _failed("moteur-absent", backend=backend)
    if not isinstance(max_seconds, (int, float)) \
            or isinstance(max_seconds, bool) \
            or not 0.0 < float(max_seconds) <= MAX_CAPTURE_SECONDS:
        return _failed("duree-invalide", backend=backend)
    directory = Path(out_dir) if out_dir is not None else Path(
        tempfile.gettempdir())
    try:
        target = directory / "wilfrid_mic_capture.3gp"
        command = ["termux-microphone-record", "-f", str(target),
                   "-d", str(int(float(max_seconds)))]
        if int(float(max_seconds)) < 1:
            command = ["termux-microphone-record", "-f", str(target)]
        completed = subprocess.run(
            command, capture_output=True, timeout=float(max_seconds) + 15.0)
    except PermissionError:
        return _failed("permission-absente", backend=backend)
    except FileNotFoundError:
        return _failed("moteur-absent", backend=backend)
    except Exception:
        return _failed("erreur-capture", backend=backend)
    try:
        if completed.returncode != 0 or not target.exists():
            return _failed("erreur-capture", backend=backend)
        raw = target.read_bytes()
    except Exception:
        return _failed("erreur-capture", backend=backend)
    finally:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
    if not raw:
        return _failed("capture-vide", backend=backend)
    if len(raw) > MAX_CAPTURE_BYTES:
        return _failed("borne-depassee", backend=backend)
    return AudioCapture(status="OK", reason="", pcm=raw, sample_rate=0,
                        frames=0, encoding="conteneur-termux-non-pcm",
                        backend=backend)


def termux_tts_speak(text: Any, *, timeout_s: Any = 20.0) -> Tuple[bool, str]:
    """Parle via le TTS système Android. `(joué, raison)` honnêtes."""
    if not isinstance(text, str) or not text.strip():
        return False, "entree-invalide"
    if len(text.strip()) > 2000:
        return False, "borne-depassee"
    if shutil.which("termux-tts-speak") is None:
        return False, "moteur-absent"
    if not isinstance(timeout_s, (int, float)) \
            or isinstance(timeout_s, bool) or float(timeout_s) <= 0.0:
        return False, "entree-invalide"
    try:
        completed = subprocess.run(
            ["termux-tts-speak", text.strip()], capture_output=True,
            timeout=min(float(timeout_s), 60.0))
    except FileNotFoundError:
        return False, "moteur-absent"
    except PermissionError:
        return False, "permission-absente"
    except Exception:
        return False, "erreur-tts"
    if completed.returncode != 0:
        return False, "erreur-tts"
    return True, "parle"


def play_pcm(pcm: Any, sample_rate: Any = DEFAULT_SAMPLE_RATE,
             *, timeout_s: Any = 20.0) -> Tuple[bool, str]:
    """Joue du PCM via sounddevice. `(joué, raison)` honnêtes."""
    if not isinstance(pcm, (bytes, bytearray)) or not bytes(pcm):
        return False, "entree-invalide"
    if len(bytes(pcm)) > MAX_CAPTURE_BYTES:
        return False, "borne-depassee"
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) \
            or not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
        return False, "entree-invalide"
    try:
        import sounddevice as sd
    except Exception:
        return False, "moteur-absent"
    try:
        import numpy as np
        samples = np.frombuffer(bytes(pcm), dtype=np.int16)
        sd.play(samples, samplerate=int(sample_rate))
        sd.wait()
    except PermissionError:
        return False, "permission-absente"
    except Exception as exc:
        message = str(exc).lower()
        if "no device" in message or "default" in message:
            return False, "peripherique-absent"
        return False, "erreur-lecture"
    return True, "joue"


def probe_backends() -> Dict[str, Any]:
    """Détection seule : présence, jamais de capture ni de lecture."""
    try:
        import sounddevice  # noqa: F401
        sd_present = True
    except Exception:
        sd_present = False
    try:
        import vosk  # noqa: F401
        stt_present: bool = True
        stt_detail = "vosk-present"
    except Exception:
        stt_present = False
        stt_detail = ("aucun-moteur-stt-local-distribue-"
                      "pour-cet-interpreteur-plateforme")
    return {"sounddevice_pcm": sd_present,
            "termux_microphone_record":
                shutil.which("termux-microphone-record") is not None,
            "termux_tts_speak":
                shutil.which("termux-tts-speak") is not None,
            "pulse_play": shutil.which("paplay") is not None,
            "stt_local_reel": stt_present,
            "stt_detail": stt_detail,
            "network": False}


def describe() -> Dict[str, Any]:
    """Capacités matérielles déclaratives (détection, sans effet)."""
    probed = probe_backends()
    return {"microphone_reel_possible": bool(probed["sounddevice_pcm"]),
            "tts_reel_possible": bool(probed["termux_tts_speak"]),
            "stt_reel_possible": bool(probed["stt_local_reel"]),
            "backends": probed,
            "bornes": {"duree_max_s": MAX_CAPTURE_SECONDS,
                       "octets_max": MAX_CAPTURE_BYTES},
            "network": False, "authority": False}
