"""Wilfrid — synthèse multi-requêtes P7 K-δ (pure, descriptive, sans autorité).

Agrège des verdicts `Coherence` issus de plusieurs `AuditRecord` en une
synthèse bornée strictement informationnelle : totaux + état global dérivé
exclusivement des verdicts, sans fait nouveau, sans résultat métier, sans
autorisation, sans regroupement implicite (ni intention, ni mission, ni
utilisateur). Une collection de traces ne prouve aucune vérité externe.

Priorité fermée : un seul INCOHERENT → synthèse INCOHERENTE ; sinon un seul
INCOMPLET (ou collection vide) → synthèse INCOMPLETE ; sinon COHERENTE.
INCOHERENT n'est jamais requalifié, l'absence n'est jamais un succès.
Aucun I/O, réseau, subprocess, état global, Governor, Approval, permission,
journal ou effet : seules `verify()` (pure) et des lectures d'attributs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from core.p7.coherence import (
    COHERENT,
    INCOHERENT,
    INCOMPLET,
    CoherenceVerdict,
    verify,
)


@dataclass(frozen=True)
class MissionSummary:
    """Synthèse bornée : totaux + état global, vocabulaire fermé."""

    total: int = 0
    coherent: int = 0
    incoherent: int = 0
    incomplete: int = 0
    state: str = INCOMPLET


def summary(records: Any) -> MissionSummary:
    """Agrège des `AuditRecord` en synthèse. Pur, déterministe, sans I/O."""
    if not isinstance(records, (tuple, list)):
        return MissionSummary()
    verdicts: Tuple[CoherenceVerdict, ...] = tuple(
        verify(record) for record in records)
    coherent = sum(1 for verdict in verdicts
                   if verdict.verdict == COHERENT)
    incoherent = sum(1 for verdict in verdicts
                     if verdict.verdict == INCOHERENT)
    incomplete = sum(1 for verdict in verdicts
                     if verdict.verdict == INCOMPLET)
    total = coherent + incoherent + incomplete
    if total == 0 or incoherent > 0:
        state = INCOHERENT if incoherent > 0 else INCOMPLET
    elif incomplete > 0:
        state = INCOMPLET
    else:
        state = COHERENT
    return MissionSummary(total=total, coherent=coherent,
                          incoherent=incoherent, incomplete=incomplete,
                          state=state)
