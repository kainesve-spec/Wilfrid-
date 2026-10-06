"""Wilfrid — journal d'accès P6.1 (borné, rotatif, champs minimaux).

Reprend le principe robuste du SessionJournal P4 (sans le modifier) :
JSONL, 64 Ko, 1 rotation, écriture best-effort. Champs strictement
limités : timestamp, action, permission, cible, décision, motif,
job_id, version de configuration. Aucune donnée sensible inutile.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

MAX_BYTES = 64 * 1024

_FIELDS = ("timestamp", "action", "permission", "target", "decision",
           "reason", "job_id", "config_version")


class AccessLog:
    """Journal d'accès. `path=None` = désactivé (aucune écriture)."""

    def __init__(self, path: Optional[Path] = None, config_version: int = 1):
        self.path = Path(path) if path is not None else None
        self.config_version = config_version
        self.enabled = path is not None

    def record(self, action: str, permission_id: str = "",
               target: str = "", decision: str = "",
               reason: str = "", job_id: str = "") -> None:
        if not self.enabled or self.path is None:
            return
        payload = {
            "timestamp": time.time(),
            "action": str(action),
            "permission": str(permission_id),
            "target": str(target)[:256],
            "decision": str(decision),
            "reason": str(reason)[:256],
            "job_id": str(job_id),
            "config_version": self.config_version,
        }
        line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_file() and (
                    self.path.stat().st_size + len(line) > MAX_BYTES):
                rotated = self.path.with_suffix(self.path.suffix + ".1")
                try:
                    if rotated.is_file():
                        rotated.unlink()
                except OSError:
                    pass
                try:
                    self.path.rename(rotated)
                except OSError:
                    return
            with open(self.path, "ab") as fh:
                fh.write(line)
        except OSError:
            pass  # best-effort : le journal ne casse jamais l'appelant

    def callback(self, **fields: Any) -> None:
        self.record(
            action=str(fields.get("action", "")),
            permission_id=str(fields.get("permission_id", "")),
            target=str(fields.get("target", "")),
            decision=str(fields.get("decision", "")),
            reason=str(fields.get("reason", "")),
            job_id=str(fields.get("job_id", "")),
        )
