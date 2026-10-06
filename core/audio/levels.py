"""Wilfrid — niveaux audio (P2.1, déplacé à l'identique depuis jarvis.py)."""

from __future__ import annotations

import numpy as np


def rms_mono(block: np.ndarray) -> float:
    if block.ndim > 1:
        block = np.mean(block.astype(np.float64), axis=1)
    else:
        block = block.astype(np.float64)
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block**2)))
