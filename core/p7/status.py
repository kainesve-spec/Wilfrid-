"""Wilfrid — vue statut P7 (lecture seule, observation pure).

Fournit à l'approbateur humain un snapshot factuel de l'état P7 avant une
éventuelle décision, sans créer aucune autorité :(score ACTIVE/DECLARED
rapportés par l'appelant, présence jail/canal/backup, capacités connues).
Aucune interprétation : présent = présent, absent = absent — jamais
« sécurisé », « sain », « autorisé », « disponible », « approuvé ».

Lecture seule d'existence (`is_dir`, jamais de contenu lu, jamais créé) sur
les seuls chemins du contrat (racine jail, `notifications/`, `.backup/`).
Aucun Governor, Approval, permission, registry, réseau, subprocess, secret,
I/O d'écriture, inférence ou état global : imports `core.p7` limités aux
constantes inertes (`resolver.jail_root`, `types.B2_IDS`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from core.p7.resolver import jail_root
from core.p7.types import B2_IDS


@dataclass(frozen=True)
class StatusSnapshot:
    """Snapshot borné : faits de présence et comptes rapportés, rien d'autre."""

    active: int = 0
    declared: int = 0
    jail_present: bool = False
    channel_present: bool = False
    backup_present: bool = False
    capabilities: Tuple[str, ...] = ()
    reason: str = "ok"


def _is_present(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def _valid_count(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def status(*, active: Any = 0, declared: Any = 0,
           jail_root: Any = None) -> StatusSnapshot:
    """Snapshot factuel P7. Pur, déterministe, lecture seule d'existence."""
    active_count = _valid_count(active)
    declared_count = _valid_count(declared)
    if active_count is None or declared_count is None:
        return StatusSnapshot(reason="invalid-input")
    try:
        root = Path(jail_root) if jail_root is not None else jail_root()
    except (TypeError, ValueError, RuntimeError, OSError):
        return StatusSnapshot(active=active_count, declared=declared_count,
                              capabilities=tuple(B2_IDS),
                              reason="invalid-root")
    if not isinstance(root, Path):
        return StatusSnapshot(active=active_count, declared=declared_count,
                              capabilities=tuple(B2_IDS),
                              reason="invalid-root")
    jail_ok = _is_present(root)
    channel_ok = _is_present(root / "notifications") if jail_ok else False
    backup_ok = _is_present(root / ".backup") if jail_ok else False
    return StatusSnapshot(active=active_count, declared=declared_count,
                          jail_present=jail_ok, channel_present=channel_ok,
                          backup_present=backup_ok,
                          capabilities=tuple(B2_IDS), reason="ok")
