"""Wilfrid — Harnais de mesure wake-word P1 (référence officielle T1).

Reproduit fidèlement le pipeline Heed documenté (cf. heed/audio.py et
heed/export.py « Deployment usage »), sans le réinventer :

    WAV mono 16 kHz (PCM16)
    → highpass Butterworth ordre 8, 100 Hz (causal sosfilt, init zi*x[0])
    → notch 50 Hz + 60 Hz, Q=30 (idem)
    → peak normalize -3 dBFS
    → trim silence (frames 20 ms, seuil relatif -40 dB)
    → peak normalize -3 dBFS (2e passe, comme Heed)
    → fenêtre 16000 samples (centrage, zero-pad / crop centré)
    → STFT n_fft=512, win=400, hop=160, Hann périodique,
      center=True (reflect-pad n_fft//2), puissance spectrale
    → mel filterbank HTK 40 bandes, 0-8000 Hz (2595*log10, triangulaire)
    → log naturel (clamp 1e-9) → CMN (moyenne temporelle par bin)
    → forme (1, 40, 101) → models/wake.onnx → logit → sigmoid
    → probabilité → comparaison au seuil lu dans models/wake.json

Usage :
    python tools/score_wavs.py <fichier.wav> [<fichier2.wav> ...]

Déterministe : mêmes entrées → mêmes sorties (aucun aléa).
Ne modifie jamais les WAV, le modèle ni le seuil.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from scipy import signal as ssig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = PROJECT_ROOT / "models" / "wake.onnx"
DEFAULT_META = PROJECT_ROOT / "models" / "wake.json"


def load_meta(meta_path: Path = DEFAULT_META) -> dict:
    """Lit les paramètres depuis wake.json (seuil, audio, mel)."""
    with open(meta_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_wav_mono16(path: str | Path) -> tuple[np.ndarray, int]:
    """Lit un WAV PCM16 mono -> (float32 /32768, sample_rate). Lecture seule."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[0:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path}: not RIFF/WAVE")
    off, sample_rate, data = 12, None, None
    while off + 8 <= len(raw):
        tag = raw[off:off + 4]
        size = struct.unpack("<I", raw[off + 4:off + 8])[0]
        body = raw[off + 8:off + 8 + size]
        if tag == b"fmt ":
            channels = struct.unpack("<H", body[2:4])[0]
            sample_rate = struct.unpack("<I", body[4:8])[0]
            bits = struct.unpack("<H", body[14:16])[0]
            if channels != 1 or bits != 16:
                raise ValueError(
                    f"{path}: need mono PCM16, got ch={channels} bits={bits}")
        elif tag == b"data":
            data = np.frombuffer(body, dtype=np.int16).astype(
                np.float32) / 32768.0
        off += 8 + size + (size & 1)
    if data is None or sample_rate is None:
        raise ValueError(f"{path}: fmt/data chunk missing")
    return np.array(data, dtype=np.float32), sample_rate


def highpass_filter(x: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """HPF Butterworth ordre 8 @100 Hz + notch 50/60 Hz Q=30 (cf. Heed)."""
    flat = np.asarray(x, dtype=np.float64).flatten()
    sos = ssig.butter(8, 100.0, btype="highpass", fs=sample_rate, output="sos")
    zi = ssig.sosfilt_zi(sos)
    flat, _ = ssig.sosfilt(sos, flat, zi=zi * flat[0])
    for freq in (50.0, 60.0):
        b, a = ssig.iirnotch(freq, 30.0, fs=sample_rate)
        sos_notch = ssig.tf2sos(b, a)
        zin = ssig.sosfilt_zi(sos_notch)
        flat, _ = ssig.sosfilt(sos_notch, flat, zi=zin * flat[0])
    return np.ascontiguousarray(flat.astype(np.float32))


def peak_normalize(x: np.ndarray, target_dbfs: float = -3.0) -> np.ndarray:
    """Met le pic à target_dbfs (cf. Heed)."""
    peak = float(np.abs(x).max())
    if peak < 1e-6:
        return x
    return (x * (10 ** (target_dbfs / 20.0) / max(peak, 1e-9))).astype(np.float32)


def trim_silence(x: np.ndarray, sample_rate: int = 16000,
                 frame_ms: float = 20.0, threshold_db: float = -40.0) -> np.ndarray:
    """Coupe le silence avant/après (seuil relatif au pic, cf. Heed)."""
    n = x.size
    frame_len = int(sample_rate * frame_ms / 1000)
    if frame_len <= 0 or n <= frame_len:
        return x
    pad = (-n) % frame_len
    padded = np.concatenate([x, np.zeros(pad, dtype=np.float32)])
    frames = padded.reshape(-1, frame_len)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    peak_rms = max(float(rms.max()), 1e-9)
    voiced = np.nonzero(rms > peak_rms * (10 ** (threshold_db / 20.0)))[0]
    if voiced.size == 0:
        return x
    return x[voiced.min() * frame_len:(voiced.max() + 1) * frame_len]


def center_in_window(x: np.ndarray, window: int = 16000) -> np.ndarray:
    """Fenêtre fixe 16000 samples, centrée (cf. Heed center_in_window)."""
    n = x.size
    if n == window:
        return x
    if n < window:
        pad_total = window - n
        left = pad_total // 2
        return np.concatenate([np.zeros(left, dtype=np.float32), x,
                               np.zeros(pad_total - left, dtype=np.float32)])
    start = (n - window) // 2
    return x[start:start + window]


def hann_periodic(n: int) -> np.ndarray:
    """Hann périodique (torch.hann_window), pas symétrique."""
    return (0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)).astype(np.float32)


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(m: float) -> float:
    return 700.0 * (10.0 ** (m / 2595.0) - 1.0)


def mel_filterbank(n_mels: int = 40, n_fft: int = 512,
                   sample_rate: int = 16000,
                   fmin: float = 0.0, fmax: float = 8000.0) -> np.ndarray:
    """Banc HTK triangulaire sans normalisation d'aire (cf. Heed)."""
    mel_pts = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz_pts = np.array([_mel_to_hz(m) for m in mel_pts])
    freqs = np.linspace(0.0, sample_rate / 2, n_fft // 2 + 1)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(n_mels):
        left, center, right = hz_pts[m], hz_pts[m + 1], hz_pts[m + 2]
        rising = (freqs - left) / (center - left + 1e-9)
        falling = (right - freqs) / (right - center + 1e-9)
        fb[m] = np.clip(np.minimum(rising, falling), 0.0, None)
    return fb


def log_mel_cmn(x: np.ndarray, sample_rate: int = 16000,
                n_fft: int = 512, win_length: int = 400,
                hop_length: int = 160, n_mels: int = 40) -> tuple[np.ndarray, int]:
    """STFT reflect+center, puissance, mel HTK, log naturel, CMN (cf. Heed)."""
    window = hann_periodic(win_length)
    fb = mel_filterbank(n_mels=n_mels, n_fft=n_fft, sample_rate=sample_rate)
    y = np.pad(x.astype(np.float64), n_fft // 2, mode="reflect")
    n_frames = 1 + (y.size - win_length) // hop_length
    spec = np.empty((n_fft // 2 + 1, n_frames))
    for t in range(n_frames):
        frame = y[t * hop_length:t * hop_length + win_length] * window
        spec[:, t] = np.abs(np.fft.rfft(frame, n=n_fft)) ** 2
    mel = fb @ spec
    out = np.log(np.clip(mel, 1e-9, None))
    out = out - out.mean(axis=-1, keepdims=True)
    return out.astype(np.float32), n_frames


def sigmoid(z: float) -> float:
    return float(1.0 / (1.0 + np.exp(-z)))


def score_file(path: str | Path, session: ort.InferenceSession,
               threshold: float, sample_rate: int = 16000,
               window_samples: int = 16000) -> dict:
    """Pipeline complet sur un WAV. Retourne les mesures (aucune écriture)."""
    audio, sr = read_wav_mono16(path)
    if sr != sample_rate:
        raise ValueError(f"{path}: sample rate {sr} != {sample_rate} "
                         f"(rééchantillonnage hors périmètre P1)")
    n_in = audio.size
    audio = highpass_filter(audio, sample_rate)
    audio = peak_normalize(audio)
    trimmed = trim_silence(audio, sample_rate)
    n_trim = trimmed.size
    audio = peak_normalize(trimmed)
    audio = center_in_window(audio, window_samples)
    mel, n_frames = log_mel_cmn(audio, sample_rate)
    logit = float(np.asarray(
        session.run(None, {"mel": mel[None]})[0]).flatten()[0])
    prob = sigmoid(logit)
    return {
        "file": Path(path).name,
        "samples_in": n_in,
        "duration_s": n_in / sample_rate,
        "samples_trimmed": n_trim,
        "mel_shape": tuple(int(v) for v in mel.shape),
        "n_frames": n_frames,
        "logit": logit,
        "prob": prob,
        "threshold": threshold,
        "trigger": bool(prob > threshold),
    }


def main(argv: list[str]) -> int:
    meta = load_meta()
    threshold = float(meta["threshold"])
    sample_rate = int(meta.get("sample_rate", 16000))
    window_samples = int(meta.get("audio_window_samples", sample_rate))
    session = ort.InferenceSession(str(DEFAULT_MODEL),
                                   providers=["CPUExecutionProvider"])
    print(f"seuil={threshold:.3f} (lu dans models/wake.json)")
    for path in argv:
        try:
            r = score_file(path, session, threshold, sample_rate, window_samples)
        except Exception as exc:
            print(f"{path}: ERREUR {type(exc).__name__}: {exc}")
            continue
        print(f"{r['file']}: samples={r['samples_in']} "
              f"dur={r['duration_s']:.3f}s trim={r['samples_trimmed']} "
              f"mel={r['mel_shape'][0]}x{r['mel_shape'][1]} "
              f"logit={r['logit']:.6f} prob={r['prob']:.6f} "
              f"seuil={r['threshold']:.3f} trigger={r['trigger']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
