"""Wilfrid — TTS local réel (voix piper upmc/pierre, offline, sans autorité).

Moteur : voix VITS `fr_FR-upmc-medium` (locuteur `pierre`, masculin),
inférée via `onnxruntime` (déjà présent) ; phonémisation via binaire
`espeak` classique (IPA, francisée) + table d'identifiants de la voix.
Fichiers hors dépôt (`~/.local/share/wilfrid/tts/`, surcharge par
environnement `WILFRID_TTS_MODEL` / `WILFRID_TTS_TOKENS` /
`WILFRID_TTS_DATA`).

Aucun import du Core : entrée = texte déjà validé, sortie = octets WAV.
Le TTS ne reçoit jamais une décision, une capability, un mandat ou une
approbation. Personnalisation vocale : état `NONE` explicite, point
d'extension documenté, aucune donnée biométrique traitée ici.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

TTS_ENGINE_NAME = "piper-vits-local"
TTS_VOICE_NAME = "upmc-pierre"
TTS_LANG_DEFAULT = "fr"
TTS_RATE_NATIVE = 22050
TTS_SID_PIERRE = 1
TTS_MAX_CHARS = 2000
TTS_MAX_WAV_BYTES = 2097152
TTS_CLAUSE_MAX = 220

_ENV_MODEL = "WILFRID_TTS_MODEL"
_ENV_TOKENS = "WILFRID_TTS_TOKENS"
_ENV_DATA = "WILFRID_TTS_DATA"

_ATTACH = set("̃ˈˌːˑ˞ˤ̧̩̪̯̺̻ʰʲ́̀̂̄")

_FRANCISATION = {
    "ɪ": "i", "ɹ": "ʁ", "ʊ": "u", "ʌ": "a", "ð": "d", "θ": "t",
    "əl": "əl", "ɚ": "ə", "ɫ": "l", "ᵻ": "i", "ɵ": "ø",
}

_CLAUSE_SPLIT = re.compile(r"(?<=[.!?…\n])\s+")


@dataclass(frozen=True)
class VoiceProfile:
    """Contrat de voix : sortie uniquement, jamais une décision d'exécution."""

    gender: str = "masculine"
    register: str = "grave"
    presence: str = "forte-calme"
    style: str = "pose-analytique"
    texture: str = "legerement-synthetique"
    articulation: str = "tres-nette"
    language: str = "fr"
    pacing: str = "modere-stable"
    emotion: str = "contenue"
    authority: str = "aucune"
    engine: str = TTS_ENGINE_NAME
    voice: str = TTS_VOICE_NAME
    sid: int = TTS_SID_PIERRE
    length_scale: float = 1.15
    noise_scale: float = 0.667
    noise_w: float = 0.8
    source: str = "synthese-neurale-locale"
    personalization_state: str = "NONE"


WILFRID_VOICE = VoiceProfile()


@dataclass(frozen=True)
class TtsResult:
    """Sortie TTS : audio + état explicite, jamais une preuve d'écoute."""

    status: str = "FAILED"
    reason: str = "moteur-absent"
    wav: bytes = b""
    sample_rate: int = 0
    seconds: float = 0.0
    engine: str = TTS_ENGINE_NAME


def _default_paths() -> Tuple[str, str, str]:
    base = Path.home() / ".local" / "share" / "wilfrid" / "tts"
    return (os.environ.get(_ENV_MODEL, str(base / "fr_FR-upmc-medium.onnx")),
            os.environ.get(_ENV_TOKENS, str(base / "tokens.txt")),
            os.environ.get(_ENV_DATA, str(base / "espeak-ng-data")))


def find_engine(model_path: Any = None, tokens_path: Any = None,
                data_dir: Any = None) -> Tuple[str, str, str, bool, str]:
    """Localise le moteur. `(modèle, tokens, data, disponible, raison)`."""
    default_model, default_tokens, default_data = _default_paths()
    model = str(model_path) if model_path else default_model
    tokens = str(tokens_path) if tokens_path else default_tokens
    data = str(data_dir) if data_dir else default_data
    if shutil.which("espeak") is None:
        return model, tokens, data, False, "moteur-absent:phonemiseur-espeak"
    if not Path(model).is_file():
        return model, tokens, data, False, "moteur-absent:modele-introuvable"
    if not Path(tokens).is_file():
        return model, tokens, data, False, "moteur-absent:tokens-introuvables"
    return model, tokens, data, True, ""


def _espeak_ipa(text: str) -> str:
    completed = subprocess.run(
        ["espeak", "--ipa", "-v", "fr", text], capture_output=True, text=True,
        timeout=30.0)
    if completed.returncode != 0:
        raise RuntimeError("espeak rc=%d" % completed.returncode)
    return completed.stdout.strip()


def _francise(ipa: str) -> Tuple[str, int]:
    cleaned = re.sub(r"\((en|fr|de|es|it|pt)\)", "", ipa)
    out: List[str] = []
    changed = 0
    for ch in cleaned:
        if ch in _FRANCISATION:
            out.append(_FRANCISATION[ch])
            changed += 1
        else:
            out.append(ch)
    return "".join(out), changed


def _tokenize(ipa: str, id_map: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    toks: List[str] = []
    dropped: List[str] = []
    buf = ""
    for ch in ipa:
        if ch in _ATTACH:
            buf += ch
            continue
        if buf:
            toks.append(buf)
            buf = ""
        if ch in id_map:
            toks.append(ch)
        elif ch in (" ", "\n", "\t"):
            toks.append(" ")
        else:
            joined = (toks[-1] + ch) if toks else ch
            if joined in id_map:
                toks[-1] = joined
            else:
                dropped.append(ch)
    if buf:
        toks.append(buf)
    return toks, dropped


def _ids_for(toks: List[str], id_map: Dict[str, Any],
             pad_ids: List[int]) -> List[int]:
    ids: List[int] = []
    space_ids = list(id_map.get(" ", [3]))
    for tok in toks:
        hit = id_map.get(tok)
        ids.extend(list(hit) if hit else space_ids)
        ids.extend(pad_ids)
    return ids


def _split_clauses(text: str) -> List[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT.split(text.strip())]
    clauses: List[str] = []
    for part in parts:
        while len(part) > TTS_CLAUSE_MAX:
            cut = part.rfind(" ", 0, TTS_CLAUSE_MAX)
            if cut <= 0:
                cut = TTS_CLAUSE_MAX
            clauses.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            clauses.append(part)
    return clauses


def _load_id_map(model_path: str, tokens_path: str) -> Dict[str, List[int]]:
    found = None
    candidates = [model_path + ".json", tokens_path]
    for candidate in candidates:
        if Path(candidate).is_file():
            try:
                data = json.loads(Path(candidate).read_text(
                    encoding="utf-8"))
                if isinstance(data, dict) and isinstance(
                        data.get("phoneme_id_map"), dict):
                    found = data["phoneme_id_map"]
                    break
            except (OSError, ValueError):
                continue
    if not found:
        raise RuntimeError("table-phonemes-introuvable")
    return {str(k): [int(i) for i in v] for k, v in found.items()}


def synthesize(text: Any, profile: Any = None, *,
               model_path: Any = None, tokens_path: Any = None,
               data_dir: Any = None,
               timeout_s: Any = 180.0) -> TtsResult:
    """Synthétise un texte validé. États honnêtes, bornes strictes."""
    if profile is None:
        profile = WILFRID_VOICE
    if not isinstance(text, str) or not text.strip():
        return TtsResult(status="SKIPPED", reason="texte-vide",
                         engine=TTS_ENGINE_NAME)
    if len(text.strip()) > TTS_MAX_CHARS:
        return TtsResult(status="FAILED", reason="borne-depassee:texte",
                         engine=TTS_ENGINE_NAME)
    model, tokens, _data, available, reason = find_engine(
        model_path, tokens_path, data_dir)
    if not available:
        return TtsResult(status="FAILED", reason=reason,
                         engine=TTS_ENGINE_NAME)
    try:
        import numpy as np
        import onnxruntime as ort
    except Exception:
        return TtsResult(status="FAILED", reason="moteur-absent:onnxruntime",
                         engine=TTS_ENGINE_NAME)
    try:
        id_map = _load_id_map(model, tokens)
    except RuntimeError as exc:
        return TtsResult(status="FAILED", reason=str(exc),
                         engine=TTS_ENGINE_NAME)
    pad_ids = [int(i) for i in id_map.get("_", [0])]
    bos = [int(i) for i in id_map.get("^", [1])]
    eos = [int(i) for i in id_map.get("$", [2])]
    try:
        sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    except Exception:
        return TtsResult(status="FAILED", reason="erreur-tts:chargement",
                         engine=TTS_ENGINE_NAME)
    clauses = _split_clauses(text.strip())
    if not clauses:
        return TtsResult(status="SKIPPED", reason="texte-vide",
                         engine=TTS_ENGINE_NAME)
    chunks: List[bytes] = []
    total_frames = 0
    try:
        sid = int(getattr(profile, "sid", TTS_SID_PIERRE))
        length_scale = float(getattr(profile, "length_scale", 1.15))
        noise_scale = float(getattr(profile, "noise_scale", 0.667))
        noise_w = float(getattr(profile, "noise_w", 0.8))
    except (TypeError, ValueError):
        return TtsResult(status="FAILED", reason="entree-invalide:profil",
                         engine=TTS_ENGINE_NAME)
    for clause in clauses:
        try:
            ipa = _espeak_ipa(clause)
        except Exception:
            return TtsResult(status="FAILED", reason="erreur-tts:phonemes",
                             engine=TTS_ENGINE_NAME)
        if not ipa:
            continue
        franc, _changed = _francise(ipa)
        toks, _dropped = _tokenize(franc, id_map)
        if not toks:
            continue
        ids = list(bos) + _ids_for(toks, id_map, pad_ids) + list(eos)
        try:
            out = sess.run(
                None,
                {"input": np.array([ids], dtype=np.int64),
                 "input_lengths": np.array([len(ids)], dtype=np.int64),
                 "scales": np.array([noise_scale, noise_w, length_scale],
                                    dtype=np.float32),
                 "sid": np.array([sid], dtype=np.int64)})
        except Exception:
            return TtsResult(status="FAILED",
                             reason="erreur-tts:synthese",
                             engine=TTS_ENGINE_NAME)
        import numpy as _np
        pcm = (_np.clip(_np.squeeze(_np.array(out[0])), -1.0, 1.0)
               * 32767).astype("<i2").tobytes()
        chunks.append(pcm)
        total_frames += len(pcm) // 2
        chunks.append(b"\x00\x00" * int(TTS_RATE_NATIVE * 0.15))
        total_frames += int(TTS_RATE_NATIVE * 0.15)
        if total_frames * 2 > TTS_MAX_WAV_BYTES:
            return TtsResult(status="FAILED",
                             reason="borne-depassee:audio",
                             engine=TTS_ENGINE_NAME)
    if not chunks:
        return TtsResult(status="FAILED", reason="erreur-tts:sans-audio",
                         engine=TTS_ENGINE_NAME)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(TTS_RATE_NATIVE)
        handle.writeframes(b"".join(chunks))
    wav = buffer.getvalue()
    seconds = total_frames / float(TTS_RATE_NATIVE)
    return TtsResult(status="OK", reason="", wav=wav,
                     sample_rate=TTS_RATE_NATIVE, seconds=seconds,
                     engine=TTS_ENGINE_NAME)


def synth_fn_for(profile: Any = None, **kwargs: Any) -> Any:
    """Fabrique `synth_fn(texte)->octets` compatible `speak()`/`audio_turn()`."""

    def synth_fn(text: Any) -> bytes:
        made = synthesize(text, profile, **kwargs)
        if made.status != "OK" or not made.wav:
            raise RuntimeError("tts:" + (made.reason or made.status))
        return made.wav

    return synth_fn


def play_wav(wav_bytes: Any, *, timeout_s: Any = 60.0) -> Tuple[bool, str]:
    """Joue des octets WAV via sounddevice. `(joué, raison)` honnêtes."""
    if not isinstance(wav_bytes, (bytes, bytearray)) or not bytes(wav_bytes):
        return False, "entree-invalide:vide"
    try:
        with wave.open(io.BytesIO(bytes(wav_bytes)), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except Exception:
        return False, "entree-invalide:wav"
    if not frames:
        return False, "entree-invalide:silence"
    try:
        import sounddevice as sd
    except Exception:
        return False, "moteur-absent:lecture"
    try:
        import numpy as np
        samples = np.frombuffer(frames, dtype=np.int16)
        sd.play(samples, samplerate=int(rate))
        sd.wait()
    except PermissionError:
        return False, "permission-absente:lecture"
    except Exception as exc:
        message = str(exc).lower()
        if "no device" in message or "default" in message:
            return False, "peripherique-absent:lecture"
        return False, "erreur-lecture"
    return True, "joue"


def describe() -> Dict[str, Any]:
    """État du TTS local (détection, sans effet)."""
    _model, _tokens, _data, available, reason = find_engine()
    return {"moteur": TTS_ENGINE_NAME, "voix": TTS_VOICE_NAME,
            "disponible": available, "raison": reason,
            "langue": TTS_LANG_DEFAULT, "offline": True,
            "personalization": "NONE", "network": False,
            "authority": False}
