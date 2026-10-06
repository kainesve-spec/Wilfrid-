"""Tests P3.3 — capture (simulée + micro réel court)."""

from __future__ import annotations

import numpy as np

from core.audio.capture import ArraySource, MicSource


def test_array_source_blocks():
    """O (partiel). buffer glissant simulé : blocs 1600, fin rembourrée."""
    data = (np.arange(5000, dtype=np.float64)).astype(np.int16)
    src = ArraySource(data)
    src.open()
    blocks = []
    while True:
        chunk = src.read()
        if chunk is None:
            break
        blocks.append(chunk)
    src.close()
    assert len(blocks) == 4  # 5000 / 1600 -> 4 blocs (dernier rembourré)
    assert all(b.shape == (1600,) and b.dtype == np.int16 for b in blocks)
    assert src.stats.blocks_received == 4
    assert src.read() is None  # fermé : None


def test_mic_open_read_close():
    """Test micro réel court (16000/mono/int16/1600)."""
    src = MicSource()
    src.open()
    try:
        assert src.stats.actual_samplerate == 16000.0
        got = 0
        for _ in range(3):
            chunk = src.read()
            if chunk is None:
                break
            assert chunk.shape == (1600,)
            got += 1
        assert got == 3
        assert src.stats.blocks_received == 3
    finally:
        src.close()
    assert src.read() is None
