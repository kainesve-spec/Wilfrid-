"""Wilfrid — vue d'audit P7 K-β (lecture seule, observation pure).

Corrèle les traces JSONL existantes par `request_id` exact, sans jamais
écrire, modifier, interpréter ni recalculer : Request → Decision → Effet →
Preuve, telles que journalisées. Aucun import de `core.*` (ni Governor, ni
Approval, ni registry, ni journaux en écriture) : ce module ne peut ni
décider, ni autoriser, ni toucher à un journal.

Règles :
- corrélation exacte sur `request_id` (chaîne) ; sans `request_id`
  exploitable, aucune pièce n'est rattachée ;
- absence ≠ échec : trace absente = présence `False` explicite ;
- lignes corrompues = comptées et ignorées, jamais d'exception ;
- champs recopiés depuis des listes fermées par journal, scalaires seuls,
  chaînes tronquées : aucun secret, aucun contenu arbitraire ;
- ordre déterministe (ordre des fichiers, journaux traités p7 → p6 →
  session) ; aucune dépendance au hash, au FS ou au temps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

MAX_STR = 256

_P7_FIELDS = ("event", "actor", "permission", "target", "decision",
              "reason", "capability_version", "risk", "timestamp")
_P6_FIELDS = ("action", "permission", "target", "decision", "reason",
              "job_id", "config_version", "timestamp")
_SESSION_FIELDS = ("event", "session_id", "cause", "state",
                   "timestamp_monotonic")


def _clean_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_STR]
    return None


def _project(entry: Dict[str, Any], fields: Tuple[str, ...]) -> Dict[str, Any]:
    projected: Dict[str, Any] = {}
    for key in fields:
        if key in entry:
            cleaned = _clean_scalar(entry[key])
            if cleaned is not None:
                projected[key] = cleaned
    return projected


def _read_matches(path: Any, request_id: str,
                  fields: Tuple[str, ...]) -> Tuple[bool, List[Dict[str, Any]], int, str]:
    """Lit un journal JSONL. Retourne (présent, pièces, corrompues, motif)."""
    if path is None:
        return False, [], 0, "journal-absent"
    try:
        candidate = Path(path)
    except (TypeError, ValueError):
        return False, [], 0, "journal-absent"
    try:
        if not candidate.is_file() or candidate.is_symlink():
            return False, [], 0, "journal-absent"
        raw = candidate.read_bytes()
    except OSError:
        return False, [], 0, "journal-illisible"
    matched: List[Dict[str, Any]] = []
    corrupt = 0
    for line in raw.split(b"\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            corrupt += 1
            continue
        if not isinstance(entry, dict):
            corrupt += 1
            continue
        rid = entry.get("request_id")
        if not isinstance(rid, str) or rid != request_id:
            continue
        matched.append(_project(entry, fields))
    return True, matched, corrupt, "ok" if matched else "sans-trace"


@dataclass(frozen=True)
class AuditRecord:
    """Vue corrélée pour un `request_id` : description de l'observable seul."""

    request_id: str = ""
    p7_present: bool = False
    p6_present: bool = False
    session_present: bool = False
    p7_events: Tuple[Dict[str, Any], ...] = ()
    p6_events: Tuple[Dict[str, Any], ...] = ()
    session_events: Tuple[Dict[str, Any], ...] = ()
    corrupt_lines: int = 0
    reason: str = ""


def audit(request_id: Any, *, p7_path: Any = None,
          p6_path: Any = None,
          session_path: Any = None) -> AuditRecord:
    """Corrèle les trois journaux par `request_id` exact. Lecture seule."""
    if not isinstance(request_id, str) or not request_id.strip() \
            or len(request_id) > 512:
        return AuditRecord(request_id="", reason="invalid-request-id")
    rid = request_id
    p7_ok, p7_matched, p7_corrupt, p7_why = _read_matches(
        p7_path, rid, _P7_FIELDS)
    p6_ok, p6_matched, p6_corrupt, p6_why = _read_matches(
        p6_path, rid, _P6_FIELDS)
    sess_ok, sess_matched, sess_corrupt, sess_why = _read_matches(
        session_path, rid, _SESSION_FIELDS)
    reasons = [w for w in (p7_why, p6_why, sess_why) if w != "ok"]
    reason = "ok" if not reasons else ";".join(
        f"{name}:{why}" for name, why in
        (("p7", p7_why), ("p6", p6_why), ("session", sess_why))
        if why != "ok")
    return AuditRecord(
        request_id=rid,
        p7_present=bool(p7_matched),
        p6_present=bool(p6_matched),
        session_present=bool(sess_matched),
        p7_events=tuple(p7_matched),
        p6_events=tuple(p6_matched),
        session_events=tuple(sess_matched),
        corrupt_lines=p7_corrupt + p6_corrupt + sess_corrupt,
        reason=reason,
    )
