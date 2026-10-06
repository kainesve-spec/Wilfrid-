"""Wilfrid — journal P7 C1 (append-only, fail-closed, distinct de P6).

Champs techniques seuls, cibles/motifs tronqués, aucun secret ni contenu
sensible. `path=None` = indisponible. Tout échec d'écriture lève
JournalUnavailable (jamais best-effort silencieux côté décision).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.p7 import errors as E

MAX_BYTES = 64 * 1024

_FIELDS = ("timestamp", "event", "actor", "request_id", "permission",
           "target", "decision", "reason", "capability_version", "risk")


class JournalUnavailable(ValueError):
    """Journal indisponible : impose DENY TOTAL côté gouverneur."""


class Journal:
    """Journal d'événements P7. `path=None` = désactivé (indisponible)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else None
        self.enabled = path is not None

    def available(self) -> bool:
        return self.enabled and self.path is not None

    def record(self, event: str, actor: str = "core",
               request_id: str = "", permission_id: str = "",
               target: str = "", decision: str = "",
               reason: str = "", capability_version: int = 0,
               risk: str = "") -> Dict[str, Any]:
        if not self.available() or self.path is None:
            raise JournalUnavailable(E.JOURNAL_UNAVAILABLE)
        payload = {
            "timestamp": time.time(),
            "event": str(event),
            "actor": str(actor),
            "request_id": str(request_id),
            "permission": str(permission_id),
            "target": str(target)[:256],
            "decision": str(decision),
            "reason": str(reason)[:256],
            "capability_version": int(capability_version),
            "risk": str(risk),
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
                except OSError as exc:
                    raise JournalUnavailable(str(exc)) from exc
                try:
                    self.path.rename(rotated)
                except OSError as exc:
                    raise JournalUnavailable(str(exc)) from exc
            with open(self.path, "ab") as fh:
                fh.write(line)
        except OSError as exc:
            raise JournalUnavailable(str(exc)) from exc
        return {k: payload[k] for k in _FIELDS}
