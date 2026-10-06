"""Wilfrid — runtime wake (P3.4). Orchestration seule, aucune action.

capture → preprocessing → fenêtre → gate → ONNX → sigmoid → trigger.
Émet uniquement via `on_wake`. Aucune connaissance de STT/TTS/mémoire.
Priorité : CORRECTNESS > ROBUSTESSE > OBSERVABILITÉ > PERFORMANCE.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import numpy as np

from core.audio.capture import ArraySource, MicSource
from core.audio.preproc import (
    RingBuffer,
    StreamingFilter,
    compute_mel,
    energy_gate_open,
    peak_normalize,
)
from core.wake.detector import DetectorState, WakeDetector, WakeRuntimeConfig
from core.wake.events import WakeDetected

log = logging.getLogger("wilfrid.wake")

MODEL_PATH_DEFAULT = "models/wake.onnx"
META_PATH_DEFAULT = "models/wake.json"
EXPECTED_MEL = (40, 101)


class WakeRuntimeError(Exception):
    """Erreur fatale explicite du runtime (modèle, config, microphone)."""


class WakeRuntime:
    """Boucle de détection : `start()` (fond) / `run_once()` / `stop()`."""

    def __init__(self, model_path: str | Path = MODEL_PATH_DEFAULT,
                 meta_path: str | Path = META_PATH_DEFAULT,
                 source=None,
                 on_wake: Optional[Callable[[WakeDetected], None]] = None,
                 block_samples: int = 1600):
        self.model_path = Path(model_path)
        self.meta_path = Path(meta_path)
        try:
            self.config = WakeRuntimeConfig.from_wake_json(self.meta_path)
        except FileNotFoundError as exc:
            raise WakeRuntimeError(f"wake.json absent: {self.meta_path}") from exc
        except (ValueError, KeyError) as exc:
            raise WakeRuntimeError(f"wake.json invalide: {exc}") from exc
        if not self.model_path.is_file():
            raise WakeRuntimeError(f"modèle absent: {self.model_path}")
        self.detector = WakeDetector(self.config, on_wake=on_wake)
        self.source = source
        self.block_samples = block_samples
        self.metrics: Dict[str, Any] = {
            "frames_received": 0,
            "audio_errors": 0,
            "underruns": 0,
            "overruns": 0,
        }
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._filter: Optional[StreamingFilter] = None
        self._ring: Optional[RingBuffer] = None
        self._session = None
        self._frame_index = 0

    # ------------------------------------------------------------ démarrage
    def _load_model(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise WakeRuntimeError("onnxruntime indisponible") from exc
        try:
            session = ort.InferenceSession(str(self.model_path),
                                           providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise WakeRuntimeError(
                f"modèle illisible: {type(exc).__name__}") from exc
        spec = session.get_inputs()[0]
        shape = tuple(int(v) for v in spec.shape[1:])
        if (spec.name != "mel" or shape != EXPECTED_MEL
                or "float" not in str(spec.type)):
            raise WakeRuntimeError(
                f"modèle inattendu: {spec.name} {spec.shape} {spec.type}")
        out_shape = tuple(int(v) for v in session.get_outputs()[0].shape[1:])
        if out_shape != ():
            raise WakeRuntimeError(
                f"sortie inattendue: {session.get_outputs()[0].shape}")
        self._session = session

    def _open_source(self) -> None:
        if self.source is None:
            self.source = MicSource(blocksize=self.block_samples)
            self._owns_source = True
        else:
            self._owns_source = False
        try:
            self.source.open()
        except Exception as exc:
            raise WakeRuntimeError(f"microphone indisponible: {exc}") from exc

    def start(self) -> None:
        """Démarre la boucle en tâche de fond (vérifications d'abord)."""
        self._load_model()
        self._open_source()
        self._filter = StreamingFilter()
        self._ring = RingBuffer()
        self._frame_index = 0
        self.detector.start()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="wake-runtime")
        self._thread.start()

    # ---------------------------------------------------------------- boucle
    @staticmethod
    def _sigmoid(logit_value: float) -> float:
        return float(1.0 / (1.0 + np.exp(-logit_value)))

    def _process_block(self, block: np.ndarray) -> Optional[WakeDetected]:
        assert self._filter is not None and self._ring is not None
        assert self._session is not None
        filt = self._filter(block)
        self._ring.push(filt)
        self.metrics["frames_received"] += 1
        if not self._ring.full():
            return None
        window = self._ring.window()
        gate_open, _diag = energy_gate_open(
            window,
            threshold_dbfs=self.config.energy_dbfs,
            band_lo=self.config.band_lo_hz,
            band_hi=self.config.band_hi_hz,
            band_min=self.config.voice_band_min,
            sample_rate=self.config.sample_rate,
        )
        normed = peak_normalize(window)
        mel, _n = compute_mel(normed)
        logit = float(np.asarray(
            self._session.run(None, {"mel": mel[None]})[0]).flatten()[0])
        prob = self._sigmoid(logit)
        self._frame_index += 1
        return self.detector.step(prob, gate_open, now=time.monotonic(),
                                  frame_index=self._frame_index)

    def _loop(self, max_blocks: Optional[int] = None) -> None:
        assert self.source is not None
        processed = 0
        while not self._stop_event.is_set():
            if max_blocks is not None and processed >= max_blocks:
                break
            try:
                block = self.source.read()
            except Exception as exc:
                self.metrics["audio_errors"] += 1
                log.warning("lecture audio: %s", type(exc).__name__)
                break
            if block is None:
                if isinstance(self.source, ArraySource):
                    break  # source simulée épuisée : fin normale
                self.metrics["audio_errors"] += 1
                continue
            try:
                self._process_block(np.asarray(block))
            except Exception as exc:
                self.metrics["audio_errors"] += 1
                log.warning("fenêtre ignorée: %s", type(exc).__name__)
            processed += 1
            stats = getattr(self.source, "stats", None)
            if stats is not None:
                self.metrics["underruns"] = int(
                    getattr(stats, "underruns", 0))
                self.metrics["overruns"] = int(
                    getattr(stats, "overruns", 0))

    def run(self, max_blocks: Optional[int] = None) -> Dict[str, Any]:
        """Boucle au premier plan (tests / usages supervisés)."""
        self._load_model()
        self._open_source()
        self._filter = StreamingFilter()
        self._ring = RingBuffer()
        self._frame_index = 0
        self.detector.start()
        self._stop_event.clear()
        try:
            self._loop(max_blocks=max_blocks)
        finally:
            self.detector.stop()
            if getattr(self, "_owns_source", False):
                try:
                    assert self.source is not None
                    self.source.close()
                except Exception:
                    pass
        return self.snapshot()

    def stop(self) -> float:
        """Arrêt < 1 s : signal + jointure bornée + fermeture stream."""
        started = time.monotonic()
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        try:
            if getattr(self, "_owns_source", False) and self.source is not None:
                self.source.close()
        except Exception:
            pass
        try:
            self.detector.stop()
        except Exception:
            pass
        return time.monotonic() - started

    def snapshot(self) -> Dict[str, Any]:
        out = dict(self.metrics)
        out.update(self.detector.metrics)
        out["current_state"] = self.detector.state.value
        out["last_probability"] = self.detector.last_probability
        out["last_event_timestamp"] = self.detector.last_event_timestamp
        out["threshold"] = self.detector.config.threshold
        return out
