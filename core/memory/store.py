"""Wilfrid — mémoire persistante (Master 4) : faits et continuité.

SQLite local dédié (fichier séparé du store Knowledge : aucune confusion
mémoire/permission/autorité). Enregistrements immuables versionnés par
écriture : `write` / `read` / `search` / `update` (nouvelle version, l'ancienne
reste traçable) / `invalidate` / `delete` (traçable).

Règles : mémoire ≠ autorisation (lire/écrire ne crée aucun droit) ; contenu
hostile = donnée inerte ; secrets refusés à l'écriture (garde heuristique
documentée, même famille que P7) ; corruption/format inconnu = comportement
sûr sans invention ; contradictions conservées, jamais arbitrées ; aucune
donnée inconnue inventée ; suppression/expiration traçable ; aucune exécution.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

KINDS = ("fact", "preference", "note", "event", "decision_record",
           "mission_state", "task_state", "observation", "reference",
           "procedural", "ephemeral")
STATUSES = ("active", "invalidated", "expired", "deleted")
FRESHNESS = ("CURRENT", "OLD", "EXPIRED", "UNKNOWN")

_SECRET_HINTS = ("secret", "credential", "passwd", "api_key", "apikey",
                 "bearer", "-----begin", "token")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL,
    session_id TEXT DEFAULT '', provenance_source TEXT DEFAULT '',
    provenance_ref TEXT DEFAULT '', created_at REAL NOT NULL,
    updated_at REAL NOT NULL, expires_at REAL,
    ttl_days REAL, status TEXT NOT NULL DEFAULT 'active',
    version INTEGER NOT NULL DEFAULT 1,
    supersedes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS memory_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL,
    event TEXT NOT NULL, at REAL NOT NULL, reason TEXT DEFAULT '');
"""


@dataclass(frozen=True)
class MemoryRecord:
    """Enregistrement : données + provenance + validité, jamais un droit."""

    id: str = ""
    kind: str = ""
    content: str = ""
    session_id: str = ""
    provenance_source: str = ""
    provenance_ref: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    expires_at: Optional[float] = None
    status: str = "active"
    version: int = 1
    freshness: str = "UNKNOWN"
    confidence_basis: str = "stated"


def _looks_secret(text: str) -> bool:
    lowered = text.lower()
    if "-----begin" in lowered and "private" in lowered:
        return True
    compact = lowered.replace(" ", "").replace("\t", "")
    for hint in ("api_key=", "apikey=", "bearer", "password=", "passwd=",
                 "motdepasse=", "token="):
        if hint in compact:
            return True
    return False


def _freshness(expires_at: Any, ttl_days: Any, updated_at: float,
               now: float) -> str:
    if expires_at is not None and now > float(expires_at):
        return "EXPIRED"
    if ttl_days is None:
        return "UNKNOWN"
    try:
        span = float(ttl_days) * 86400.0
    except (TypeError, ValueError):
        return "UNKNOWN"
    if span <= 0.0:
        return "UNKNOWN"
    age = max(0.0, now - float(updated_at))
    return "CURRENT" if age <= span / 2.0 else "OLD"


class MemoryStore:
    """Persistance locale dédiée. SQLite fichier ou `:memory:` (tests)."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        try:
            self._conn = sqlite3.connect(self.path)
        except sqlite3.Error as exc:
            raise ValueError(f"mémoire inaccessible: {exc}")
        self._conn.row_factory = sqlite3.Row
        try:
            with self._conn:
                self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise ValueError(f"schéma mémoire invalide: {exc}")

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def _event(self, memory_id: str, event: str, reason: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO memory_events(memory_id, event, at, reason)"
                " VALUES (?,?,?,?)",
                (memory_id, event, time.time(), reason[:256]))

    def _row_to_record(self, row: Any, now: float) -> MemoryRecord:
        return MemoryRecord(
            id=str(row["id"]), kind=str(row["kind"]),
            content=str(row["content"]),
            session_id=str(row["session_id"] or ""),
            provenance_source=str(row["provenance_source"] or ""),
            provenance_ref=str(row["provenance_ref"] or ""),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            expires_at=(float(row["expires_at"])
                        if row["expires_at"] is not None else None),
            status=str(row["status"]), version=int(row["version"]),
            freshness=_freshness(row["expires_at"], None
                                 if "ttl_days" not in row.keys()
                                 else row["ttl_days"],
                                 float(row["updated_at"]), now))

    def write(self, record_id: str, kind: str, content: str, *,
              session_id: str = "", provenance_source: str = "",
              provenance_ref: str = "", ttl_days: Optional[float] = None,
              expires_at: Optional[float] = None) -> Tuple[bool, str]:
        """Écrit un fait. Refus contrôlés : secret, vide, kind inconnu."""
        if kind not in KINDS:
            return False, "kind-inconnu"
        if not isinstance(content, str) or not content.strip() \
                or len(content) > 4000:
            return False, "contenu-invalide"
        if not isinstance(record_id, str) or not record_id.strip() \
                or len(record_id) > 128:
            return False, "id-invalide"
        if _looks_secret(content):
            return False, "secret-refuse"
        if ttl_days is not None and (
                not isinstance(ttl_days, (int, float))
                or isinstance(ttl_days, bool)
                or not 0.0 < float(ttl_days) <= 3650.0):
            return False, "ttl-invalide"
        now = time.time()
        computed_expiry: Optional[float] = None
        if expires_at is not None:
            try:
                computed_expiry = float(expires_at)
            except (TypeError, ValueError):
                return False, "expiration-invalide"
        elif ttl_days is not None:
            computed_expiry = now + float(ttl_days) * 86400.0
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO memories(id, kind, content, session_id,"
                    " provenance_source, provenance_ref, created_at,"
                    " updated_at, expires_at, ttl_days, status, version)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (record_id.strip(), kind, content.strip(), session_id,
                     provenance_source, provenance_ref, now, now,
                     computed_expiry,
                     float(ttl_days) if ttl_days is not None else None,
                     "active", 1))
        except sqlite3.IntegrityError:
            return False, "id-existant"
        except sqlite3.Error:
            return False, "stockage-indisponible"
        try:
            self._event(record_id, "created")
        except sqlite3.Error:
            pass
        return True, "ok"

    def read(self, record_id: str,
             now: Optional[float] = None) -> Optional[MemoryRecord]:
        """Lecture par id. Absent/corrompu → None, jamais d'invention."""
        moment = float(now) if isinstance(now, (int, float)) else time.time()
        try:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id=?", (record_id,)).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        try:
            return self._row_to_record(row, moment)
        except (KeyError, TypeError, ValueError):
            return None

    def search(self, query: str, *, kind: str = "",
               limit: int = 10,
               now: Optional[float] = None) -> List[MemoryRecord]:
        """Recherche bornée par sous-chaîne (LIKE échappé), ordre stable."""
        moment = float(now) if isinstance(now, (int, float)) else time.time()
        if not isinstance(query, str) or not query.strip() or limit < 1:
            return []
        pattern = "%" + query.strip().replace(
            "%", "").replace("_", "")[:200] + "%"
        sql = ("SELECT * FROM memories WHERE content LIKE ? ESCAPE '\\'")
        params: List[Any] = [pattern]
        if kind:
            if kind not in KINDS:
                return []
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY id LIMIT ?"
        params.append(min(int(limit), 100))
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            return []
        records = []
        for row in rows:
            try:
                records.append(self._row_to_record(row, moment))
            except (KeyError, TypeError, ValueError):
                continue
        return records

    def update(self, record_id: str, content: str,
               reason: str = "") -> Tuple[bool, str]:
        """Nouvelle version : l'ancienne reste traçable via les événements."""
        current = self.read(record_id)
        if current is None:
            return False, "introuvable"
        if current.status != "active":
            return False, f"statut-{current.status}"
        if not isinstance(content, str) or not content.strip() \
                or len(content) > 4000:
            return False, "contenu-invalide"
        if _looks_secret(content):
            return False, "secret-refuse"
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE memories SET content=?, updated_at=?,"
                    " version=version+1 WHERE id=?",
                    (content.strip(), time.time(), record_id))
        except sqlite3.Error:
            return False, "stockage-indisponible"
        try:
            self._event(record_id, "updated", reason)
        except sqlite3.Error:
            pass
        return True, "ok"

    def invalidate(self, record_id: str,
                   reason: str = "") -> Tuple[bool, str]:
        """Invalidation traçable (le contenu reste lisible, marqué)."""
        current = self.read(record_id)
        if current is None:
            return False, "introuvable"
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE memories SET status='invalidated',"
                    " updated_at=? WHERE id=?", (time.time(), record_id))
        except sqlite3.Error:
            return False, "stockage-indisponible"
        try:
            self._event(record_id, "invalidated", reason)
        except sqlite3.Error:
            pass
        return True, "ok"

    def delete(self, record_id: str, reason: str = "") -> Tuple[bool, str]:
        """Suppression traçable : ligne retirée, événement conservé."""
        current = self.read(record_id)
        if current is None:
            return False, "introuvable"
        try:
            with self._conn:
                self._conn.execute("DELETE FROM memories WHERE id=?",
                                   (record_id,))
        except sqlite3.Error:
            return False, "stockage-indisponible"
        try:
            self._event(record_id, "deleted", reason)
        except sqlite3.Error:
            pass
        return True, "ok"

    def list_active(self, kind: str = "",
                    limit: int = 100,
                    statuses: Tuple[str, ...] = ("active",)
                    ) -> List[Dict[str, Any]]:
        """Enregistrements par statuts (défaut : actifs), ordre stable."""
        wanted = tuple(s for s in statuses
                       if s in ("active", "invalidated", "expired", "deleted"))
        if not wanted:
            return []
        marks = ",".join("?" for _ in wanted)
        sql = f"SELECT * FROM memories WHERE status IN ({marks})"
        params: List[Any] = list(wanted)
        if kind:
            if kind not in KINDS:
                return []
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY id LIMIT ?"
        params.append(max(1, min(int(limit), 100)))
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error:
            return []
        return [dict(r) for r in rows]

    def events(self, record_id: str) -> List[Dict[str, Any]]:
        """Journal d'un enregistrement (création/màj/invalidation/suppression)."""
        try:
            rows = self._conn.execute(
                "SELECT event, at, reason FROM memory_events"
                " WHERE memory_id=? ORDER BY seq",
                (record_id,)).fetchall()
        except sqlite3.Error:
            return []
        return [dict(r) for r in rows]
