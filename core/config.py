"""Wilfrid — constantes audio du noyau (P2.1).

Source unique de vérité pour les constantes nécessaires aux modules
`core.audio`, déplacées à l'identique depuis `jarvis.py`.
`jarvis.py` les réimporte (wrappers) : aucune valeur modifiée.
"""

from __future__ import annotations

SAMPLE_RATE = 44100
BLOCK_MS = 40
CHANNELS = 1
INPUT_PROBE_S = 0.5
INPUT_SILENT_RMS = 0.001
