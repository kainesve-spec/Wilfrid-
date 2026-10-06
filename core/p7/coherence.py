"""Wilfrid — vérificateur de cohérence P7 K-γ (fonction pure, sans I/O).

Évalue des `AuditRecord` déjà corrélés (cf. `core/p7/audit.py`) et rend un
verdict fermé, sans jamais lire un journal, appeler le Governor, toucher une
Approval/permission/registry, ni produire d'effet :
- COHERENT : traces présentes, sans contradiction explicite ;
- INCOHERENT : contradiction explicite entre traces observées ;
- INCOMPLET : information insuffisante (absence ≠ échec, jamais d'inférence).

Règle d'incohérence unique et explicite : même couple (event,
capability_version) journalisé avec deux décisions différentes pour le même
`request_id`. Séquences normales (pre-* ALLOW puis error DENY, versions
croissantes) ne sont jamais des contradictions. Lignes corrompues ou absence
de trace décisionnelle = INCOMPLET, jamais FAIL ni SUCCESS supposé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

COHERENT = "COHERENT"
INCOHERENT = "INCOHERENT"
INCOMPLET = "INCOMPLET"


@dataclass(frozen=True)
class CoherenceVerdict:
    """Verdict : vocabulaire fermé + motif + contrôles effectués."""

    verdict: str = INCOMPLET
    reason: str = ""
    checks: Tuple[str, ...] = ()


def _event_key(event: Any) -> Tuple[str, Any]:
    if not isinstance(event, dict):
        return ("", None)
    name = event.get("event")
    version = event.get("capability_version")
    if not isinstance(name, str):
        return ("", None)
    if version is None or isinstance(version, (str, int, float, bool)):
        return (name, version)
    return (name, repr(version))


def verify(record: Any) -> CoherenceVerdict:
    """Vérifie un enregistrement corrélé. Pur, déterministe, sans I/O."""
    request_id = getattr(record, "request_id", None)
    if not isinstance(request_id, str) or not request_id:
        return CoherenceVerdict(INCOMPLET, "invalid-record",
                                ("record-shape",))
    p7_events = getattr(record, "p7_events", None)
    if not isinstance(p7_events, tuple):
        try:
            p7_events = tuple(p7_events)
        except TypeError:
            return CoherenceVerdict(INCOMPLET, "invalid-record",
                                    ("record-shape",))
    seen: dict = {}
    for event in p7_events:
        key = _event_key(event)
        if key[0] == "":
            continue
        decision = event.get("decision") if isinstance(event, dict) else None
        if key in seen and seen[key] != decision:
            return CoherenceVerdict(
                INCOHERENT, "conflicting-decisions",
                ("contradiction-scan",))
        seen[key] = decision
    if not p7_events:
        return CoherenceVerdict(INCOMPLET, "no-decision-trace",
                                ("contradiction-scan", "presence"))
    corrupt = getattr(record, "corrupt_lines", 0)
    if not isinstance(corrupt, int) or isinstance(corrupt, bool):
        corrupt = 0
    if corrupt > 0:
        return CoherenceVerdict(INCOMPLET, "partial-observation",
                                ("contradiction-scan", "presence",
                                 "completeness"))
    return CoherenceVerdict(COHERENT, "ok",
                            ("contradiction-scan", "presence",
                             "completeness"))


def verify_many(records: Any) -> Tuple[CoherenceVerdict, ...]:
    """Vérifie une séquence dans l'ordre (déterministe)."""
    if not isinstance(records, (tuple, list)):
        return (CoherenceVerdict(INCOMPLET, "invalid-record",
                                  ("record-shape",)),)
    return tuple(verify(record) for record in records)
