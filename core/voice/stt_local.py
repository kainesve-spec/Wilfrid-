"""Wilfrid — adaptateur STT local réel (whisper.cpp, offline, sans autorité).

Enveloppe le binaire local `whisper-cli` + modèle `ggml-base.bin` installés
hors dépôt (`~/.local/share/wilfrid/stt/`, surcharge par environnement
`WILFRID_STT_BIN` / `WILFRID_STT_MODEL`). Aucun import du Core : entrée
audio, sortie texte + statut + détail. Confiance non fournie par le moteur :
`None` honnête (le contrat l'autorise, jamais de certitude inventée).

Règles : moteur absent = `moteur-absent` explicite ; parole absente =
`UNCERTAIN` ; tout échec = `FAILED` avec raison ; aucune logique
d'autorisation ; aucun réseau (binaire local uniquement).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

STT_STATUSES = ("OK", "UNCERTAIN", "FAILED")
STT_ENGINE_NAME = "whisper.cpp-local"
STT_LANG_DEFAULT = "fr"
STT_THREADS_DEFAULT = 4
STT_TIMEOUT_DEFAULT = 120.0
STT_MAX_WAV_BYTES = 1048576
STT_RATE_REQUIRED = 16000

_ENV_BIN = "WILFRID_STT_BIN"
_ENV_MODEL = "WILFRID_STT_MODEL"


def _default_paths() -> Tuple[str, str]:
    base = Path.home() / ".local" / "share" / "wilfrid" / "stt"
    return str(base / "whisper-cli"), str(base / "ggml-base.bin")


def find_engine(bin_path: Any = None,
                model_path: Any = None) -> Tuple[str, str, bool, str]:
    """Localise le moteur. `(binaire, modèle, disponible, raison)`."""
    default_bin, default_model = _default_paths()
    binary = str(bin_path) if bin_path else os.environ.get(_ENV_BIN, "")
    model = str(model_path) if model_path else os.environ.get(_ENV_MODEL, "")
    if not binary:
        binary = default_bin
    if not model:
        model = default_model
    if not Path(binary).is_file():
        return binary, model, False, "moteur-absent:binaire-introuvable"
    if not Path(model).is_file():
        return binary, model, False, "moteur-absent:modele-introuvable"
    return binary, model, True, ""


def _clean_text(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\[.*\]", stripped):
            continue
        lines.append(stripped)
    return " ".join(lines).strip()


def transcribe_wav(wav_path: Any, *, lang: Any = STT_LANG_DEFAULT,
                   threads: Any = STT_THREADS_DEFAULT,
                   timeout_s: Any = STT_TIMEOUT_DEFAULT,
                   bin_path: Any = None,
                   model_path: Any = None) -> Tuple[str, str, str]:
    """Transcrit un WAV 16 kHz. `(statut, texte, détail)` honnêtes."""
    binary, model, available, reason = find_engine(bin_path, model_path)
    if not available:
        return "FAILED", "", reason
    if not isinstance(wav_path, (str, Path)) or not Path(wav_path).is_file():
        return "FAILED", "", "entree-invalide:fichier-absent"
    try:
        size = Path(wav_path).stat().st_size
    except OSError:
        return "FAILED", "", "entree-invalide:illisible"
    if size <= 0 or size > STT_MAX_WAV_BYTES:
        return "FAILED", "", "borne-depassee:fichier"
    language = str(lang).strip() if isinstance(lang, str) else ""
    if not language or len(language) > 16:
        return "FAILED", "", "entree-invalide:langue"
    try:
        count = int(threads)
    except (TypeError, ValueError):
        return "FAILED", "", "entree-invalide:threads"
    if not 1 <= count <= 16:
        return "FAILED", "", "entree-invalide:threads"
    if not isinstance(timeout_s, (int, float)) \
            or isinstance(timeout_s, bool) or float(timeout_s) <= 0.0:
        return "FAILED", "", "entree-invalide:delai"
    try:
        with tempfile.TemporaryDirectory(prefix="wilfrid_stt_") as tmp:
            prefix = str(Path(tmp) / "out")
            completed = subprocess.run(
                [binary, "-m", model, "-f", str(wav_path), "-t",
                 str(count), "-l", language, "-otxt", "-of", prefix],
                capture_output=True,
                timeout=min(float(timeout_s), 600.0))
            if completed.returncode != 0:
                return "FAILED", "", "erreur-stt:code-%d" % (
                    completed.returncode)
            text_file = Path(prefix + ".txt")
            if not text_file.is_file():
                return "FAILED", "", "erreur-stt:sans-sortie"
            raw = text_file.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "FAILED", "", "moteur-absent:binaire-inexecutable"
    except PermissionError:
        return "FAILED", "", "permission-absente:moteur"
    except subprocess.TimeoutExpired:
        return "FAILED", "", "erreur-stt:delai-depasse"
    except Exception:
        return "FAILED", "", "erreur-stt:execution"
    text = _clean_text(raw)
    if not text:
        return "UNCERTAIN", "", "pas-de-parole"
    if len(text) > 2000:
        return "FAILED", "", "borne-depassee:transcription"
    return "OK", text, "moteur:%s" % STT_ENGINE_NAME


def write_pcm_wav(pcm: Any, sample_rate: Any,
                  directory: Any = None) -> Tuple[bool, str]:
    """Écrit un PCM s16le mono 16 kHz borné vers un WAV. `(ok, chemin/raison)`."""
    if not isinstance(pcm, (bytes, bytearray)) or not bytes(pcm):
        return False, "entree-invalide:vide"
    if len(bytes(pcm)) > STT_MAX_WAV_BYTES:
        return False, "borne-depassee:pcm"
    if sample_rate != STT_RATE_REQUIRED:
        return False, "format-invalide:frequence-requise-16000"
    try:
        target_dir = Path(directory) if directory is not None else Path(
            tempfile.gettempdir())
        target = target_dir / "wilfrid_stt_in.wav"
        with wave.open(str(target), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(STT_RATE_REQUIRED)
            handle.writeframes(bytes(pcm))
    except Exception:
        return False, "erreur-stt:ecriture-wav"
    return True, str(target)


def stt_fn_for(*, lang: Any = STT_LANG_DEFAULT,
               threads: Any = STT_THREADS_DEFAULT,
               timeout_s: Any = STT_TIMEOUT_DEFAULT,
               bin_path: Any = None,
               model_path: Any = None) -> Any:
    """Fabrique `stt_fn(audio_ref)` compatible `transcribe()`/`voice_turn()`.

    `audio_ref` : octets PCM s16le mono 16 kHz, chemin WAV, ou objet avec
    `.pcm`/`.sample_rate`/`.encoding`. Échec → lève (mappé FAILED honnête).
    """

    def stt_fn(audio_ref: Any) -> Tuple[str, None]:
        pcm: Any = None
        rate: Any = STT_RATE_REQUIRED
        if isinstance(audio_ref, (bytes, bytearray)):
            pcm, rate = bytes(audio_ref), STT_RATE_REQUIRED
        elif isinstance(audio_ref, (str, Path)) \
                and Path(audio_ref).is_file():
            status, text, _ = transcribe_wav(
                audio_ref, lang=lang, threads=threads, timeout_s=timeout_s,
                bin_path=bin_path, model_path=model_path)
            if status != "OK":
                raise RuntimeError("stt:" + status)
            return text, None
        elif hasattr(audio_ref, "pcm"):
            encoding = str(getattr(audio_ref, "encoding", ""))
            if encoding != "pcm-s16le-mono":
                raise RuntimeError("stt:format-non-pcm")
            pcm = getattr(audio_ref, "pcm")
            rate = getattr(audio_ref, "sample_rate", 0)
        else:
            raise RuntimeError("stt:audio-invalide")
        ok, target = write_pcm_wav(pcm, rate)
        if not ok:
            raise RuntimeError("stt:" + target)
        try:
            status, text, _ = transcribe_wav(
                target, lang=lang, threads=threads, timeout_s=timeout_s,
                bin_path=bin_path, model_path=model_path)
        finally:
            try:
                Path(target).unlink(missing_ok=True)
            except OSError:
                pass
        if status != "OK":
            raise RuntimeError("stt:" + status)
        return text, None

    return stt_fn


def describe() -> Dict[str, Any]:
    """État du STT local (détection, sans effet)."""
    _, _, available, reason = find_engine()
    return {"moteur": STT_ENGINE_NAME, "disponible": available,
            "raison": reason, "langue_defaut": STT_LANG_DEFAULT,
            "confiance_fournie": False, "network": False,
            "authority": False}
