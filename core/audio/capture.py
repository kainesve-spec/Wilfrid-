"""Wilfrid — capture audio (P3.3). Sources interchangeables.

MicSource : microphone réel via sounddevice (lecture bloquante,
16000 Hz / mono / int16 / blocs 1600 = 100 ms, validé Exp J).
ArraySource : source simulée depuis un tableau (tests, flux WAV),
même contrat, sans matériel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import numpy as np

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SAMPLES = 1600


@dataclass
class CaptureStats:
    blocks_received: int = 0
    underruns: int = 0
    overruns: int = 0
    audio_errors: List[str] = field(default_factory=list)
    device_name: Optional[str] = None
    actual_samplerate: Optional[float] = None


class MicSource:
    """Microphone réel. `open()` explicite, `read()` borné, `close()` sûr."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS,
                 dtype: str = DTYPE, blocksize: int = BLOCK_SAMPLES,
                 device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.blocksize = blocksize
        self.device = device
        self.stats = CaptureStats()
        self._stream = None
        self._opened = False

    def open(self) -> None:
        import sounddevice as sd

        if self._opened:
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.blocksize,
                device=self.device,
            )
            self._stream.start()
        except Exception as exc:
            self.stats.audio_errors.append(f"open: {type(exc).__name__}")
            raise RuntimeError(f"microphone indisponible: {type(exc).__name__}")
        try:
            info = sd.query_devices(self._stream.device)
            self.stats.device_name = str(info.get("name", ""))
        except Exception:
            pass
        self.stats.actual_samplerate = float(
            getattr(self._stream, "samplerate", 0.0) or 0.0)
        self._opened = True

    def read(self) -> Optional[np.ndarray]:
        """Un bloc int16, ou None sur erreur non fatale (comptée)."""
        if not self._opened or self._stream is None:
            return None
        try:
            data, overflowed = self._stream.read(self.blocksize)
        except Exception as exc:
            self.stats.audio_errors.append(f"read: {type(exc).__name__}")
            return None
        self.stats.blocks_received += 1
        if overflowed:
            self.stats.overruns += 1
        return np.asarray(data).flatten()

    def close(self) -> None:
        stream, self._stream = self._stream, None
        self._opened = False
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception as exc:
                self.stats.audio_errors.append(f"close: {type(exc).__name__}")

    def __enter__(self) -> "MicSource":
        self.open()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


class ArraySource:
    """Source simulée depuis un tableau int16 (tests / flux WAV)."""

    def __init__(self, samples: np.ndarray, blocksize: int = BLOCK_SAMPLES):
        self._samples = np.asarray(samples, dtype=np.int16).flatten()
        self.blocksize = blocksize
        self.stats = CaptureStats(device_name="simulated",
                                  actual_samplerate=float(SAMPLE_RATE))
        self._pos = 0
        self._opened = False

    def open(self) -> None:
        self._pos = 0
        self._opened = True

    def read(self) -> Optional[np.ndarray]:
        if not self._opened:
            return None
        if self._pos >= self._samples.size:
            return None
        chunk = self._samples[self._pos:self._pos + self.blocksize]
        self._pos += chunk.size
        if chunk.size < self.blocksize:
            chunk = np.concatenate(
                [chunk, np.zeros(self.blocksize - chunk.size, dtype=np.int16)])
        self.stats.blocks_received += 1
        return chunk

    def close(self) -> None:
        self._opened = False
