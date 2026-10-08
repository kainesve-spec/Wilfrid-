"""Wilfrid — store SQLite P6.1 (schéma minimal extensible + FTS5).

Tables : sources, documents (hash SHA-256 unique), sections, chunks
(+ chunks_fts), analyses, syntheses, provenance, citations, jobs,
permissions, whitelist, access_log. Transactions atomiques, upserts
idempotents, relations par clés étrangères. Pas d'embeddings.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, domain TEXT NOT NULL, added_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id),
    title TEXT DEFAULT '', author TEXT DEFAULT '',
    sha256 TEXT NOT NULL UNIQUE, acquired_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACQUIRED', path TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    ordinal INTEGER NOT NULL, title TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    section_id TEXT REFERENCES sections(id), ordinal INTEGER NOT NULL,
    text TEXT NOT NULL, created_at REAL NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED, text, tokenize='unicode61');
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY, chunk_id TEXT NOT NULL REFERENCES chunks(id),
    kind TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL,
    UNIQUE(chunk_id, kind));
CREATE TABLE IF NOT EXISTS syntheses (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    level TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS provenance (
    id TEXT PRIMARY KEY, claim TEXT NOT NULL, chunk_id TEXT REFERENCES chunks(id),
    document_id TEXT NOT NULL REFERENCES documents(id),
    location TEXT DEFAULT '', verified_at REAL, status TEXT DEFAULT 'unverified');
CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY, provenance_id TEXT NOT NULL REFERENCES provenance(id),
    ref TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
    document_id TEXT REFERENCES documents(id),
    completed_steps TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, scope TEXT DEFAULT '',
    version INTEGER NOT NULL, reason TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS whitelist (
    domain TEXT PRIMARY KEY, status TEXT NOT NULL, added_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, action TEXT NOT NULL,
    permission TEXT DEFAULT '', target TEXT DEFAULT '', decision TEXT NOT NULL,
    reason TEXT DEFAULT '', job_id TEXT DEFAULT '');
"""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class KnowledgeStore:
    """SQLite local. `:memory:` pour tests, fichier sinon. FTS5 exigé."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_SCHEMA)
        try:
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS __fts_probe "
                "USING fts5(x)")
            self._conn.execute("DROP TABLE IF EXISTS __fts_probe")
        except sqlite3.Error as exc:
            raise RuntimeError(f"FTS5 indisponible: {exc}")

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # ---------------------------------------------------------- documents
    def upsert_document(self, doc_id: str, sha256: str,
                        source_id: Optional[str] = None,
                        title: str = "", author: str = "",
                        status: str = "ACQUIRED", path: str = "") -> str:
        now = time.time()
        with self._conn:
            self._conn.execute(
                "INSERT INTO documents(id, source_id, title, author, sha256,"
                " acquired_at, status, path) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status",
                (doc_id, source_id, title, author, sha256, now, status,
                 path))
        return doc_id

    def add_chunk(self, chunk_id: str, document_id: str, ordinal: int,
                  text: str, section_id: Optional[str] = None) -> str:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO chunks(id, document_id, section_id,"
                " ordinal, text, created_at) VALUES (?,?,?,?,?,?)",
                (chunk_id, document_id, section_id, ordinal, text,
                 time.time()))
            self._conn.execute(
                "INSERT OR IGNORE INTO chunks_fts(chunk_id, text)"
                " VALUES (?,?)", (chunk_id, text))
        return chunk_id

    def search_chunks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            rows = self._conn.execute(
                "SELECT chunk_id AS id, text FROM chunks_fts WHERE chunks_fts"
                " MATCH ? LIMIT ?", (query, limit)).fetchall()
        except sqlite3.OperationalError:
            return []  # syntaxe FTS hostile : fail-closed, jamais d'erreur SQL
        return [dict(r) for r in rows]

    def search_chunks_in_doc(self, query: str, document_id: str,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Recherche FTS restreinte à un ouvrage (Q/R mono-document)."""
        try:
            rows = self._conn.execute(
                "SELECT f.chunk_id AS id, f.text FROM chunks_fts f"
                " JOIN chunks c ON c.id = f.chunk_id"
                " WHERE f.chunks_fts MATCH ? AND c.document_id = ? LIMIT ?",
                (query, document_id, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def document_status(self, doc_id: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT status FROM documents WHERE id=?", (doc_id,)).fetchone()
        return row["status"] if row else None

    def list_documents(self) -> List[Dict[str, Any]]:
        """Énumération lecture seule des ouvrages (ordre stable par id).

        Ajout O2 : l'abstraction n'offrait aucune énumération ; la sélection
        de source l'exige. Aucun schéma modifié, aucune écriture.
        """
        rows = self._conn.execute(
            "SELECT d.id AS id, d.source_id AS source_id, s.domain AS source,"
            " d.title AS title, d.status AS status,"
            " d.acquired_at AS acquired_at FROM documents d"
            " LEFT JOIN sources s ON s.id = d.source_id"
            " ORDER BY d.id").fetchall()
        return [dict(r) for r in rows]

    def chunk_document(self, chunk_id: str) -> Optional[str]:
        """Document parent d'un chunk (lecture seule, ajout O2)."""
        row = self._conn.execute(
            "SELECT document_id FROM chunks WHERE id=?",
            (chunk_id,)).fetchone()
        return str(row["document_id"]) if row else None

    def set_document_status(self, doc_id: str, status: str) -> None:
        with self._conn:
            cur = self._conn.execute(
                "UPDATE documents SET status=? WHERE id=?", (status, doc_id))
            if cur.rowcount == 0:
                raise ValueError(f"document inconnu: {doc_id}")

    def document_sha(self, doc_id: str) -> Optional[str]:
        """Empreinte stockée d'un document (None si inconnu)."""
        row = self._conn.execute(
            "SELECT sha256 FROM documents WHERE id=?", (doc_id,)).fetchone()
        return str(row["sha256"]) if row else None

    def delete_document_chunks(self, doc_id: str) -> int:
        """Retire chunks + index + provenance d'un document (re-ingestion).

        Retourne le nombre de chunks retirés. Opération bornée à un seul
        document ; les autres documents et le journal sont intacts.
        """
        with self._conn:
            self._conn.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN "
                "(SELECT id FROM chunks WHERE document_id=?)", (doc_id,))
            self._conn.execute(
                "DELETE FROM provenance WHERE document_id=?", (doc_id,))
            cur = self._conn.execute(
                "DELETE FROM chunks WHERE document_id=?", (doc_id,))
            return cur.rowcount

    def count_chunks(self, document_id: str = "") -> int:
        """Nombre de chunks (total ou par document). Lecture seule."""
        if document_id:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM chunks WHERE document_id=?",
                (document_id,)).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM chunks").fetchone()
        return int(row["n"]) if row else 0

    # --------------------------------------------------------------- jobs
    def create_job(self, job_id: str, kind: str,
                   document_id: Optional[str] = None) -> str:
        with self._conn:
            self._conn.execute(
                "INSERT INTO jobs(id, kind, status, document_id,"
                " completed_steps, updated_at) VALUES (?,?,?,?,?,?)",
                (job_id, kind, "QUEUED", document_id, "[]", time.time()))
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        import json

        row = self._conn.execute(
            "SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        job = dict(row)
        job["completed_steps"] = json.loads(job["completed_steps"])
        return job

    def set_job_status(self, job_id: str, status: str,
                       completed_steps: Optional[list] = None) -> None:
        import json

        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"job inconnu: {job_id}")
        steps = (completed_steps if completed_steps is not None
                 else job["completed_steps"])
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET status=?, completed_steps=?,"
                " updated_at=? WHERE id=?",
                (status, json.dumps(steps), time.time(), job_id))

    # --------------------------------------------------------- permissions
    def save_permission(self, pid: str, enabled: bool, scope: str = "",
                        version: int = 1, reason: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO permissions(id, enabled, scope, version, reason)"
                " VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET"
                " enabled=excluded.enabled, scope=excluded.scope,"
                " version=excluded.version, reason=excluded.reason",
                (pid, int(enabled), scope, version, reason))

    def load_permission(self, pid: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM permissions WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None

    def save_whitelist(self, domain: str, status: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO whitelist(domain, status, added_at)"
                " VALUES (?,?,?) ON CONFLICT(domain) DO UPDATE SET"
                " status=excluded.status",
                (domain, status, time.time()))

    def load_whitelist(self, domain: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT status FROM whitelist WHERE domain=?", (domain,)).fetchone()
        return row["status"] if row else None

    def add_provenance(self, prov_id: str, claim: str, chunk_id: str,
                       document_id: str, location: str = "") -> str:
        """Lien traçable chunk→document (idempotent ; page absente = "")."""
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO provenance(id, claim, chunk_id,"
                " document_id, location, status) VALUES (?,?,?,?,?,?)",
                (prov_id, claim, chunk_id, document_id, location,
                 "unverified"))
        return prov_id

    def chunk_provenance(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Remonte chunk → section/page → document → SHA → source."""
        row = self._conn.execute(
            "SELECT p.id, p.claim, p.chunk_id, p.location, p.status,"
            " d.id AS document_id, d.sha256, d.source_id, d.acquired_at,"
            " d.status AS doc_status FROM provenance p"
            " JOIN documents d ON d.id = p.document_id"
            " WHERE p.chunk_id=?", (chunk_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def save_analysis(self, analysis_id: str, chunk_id: str,
                      content_json: str) -> None:
        """Persiste une analyse (idempotent par UNIQUE chunk+kind)."""

        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO analyses(id, chunk_id, kind,"
                " content, created_at) VALUES (?,?,?,?,?)",
                (analysis_id, chunk_id, "p64-analysis", content_json,
                 time.time()))

    def save_synthesis(self, synthesis_id: str, document_id: str,
                       level: str, content_json: str) -> None:
        """Persiste une synthèse (idempotent par id)."""

        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO syntheses(id, document_id, level,"
                " content, created_at) VALUES (?,?,?,?,?)",
                (synthesis_id, document_id, level, content_json,
                 time.time()))

    def get_synthesis(self, document_id: str, level: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT content FROM syntheses WHERE document_id=? AND level=?",
            (document_id, level)).fetchone()
        return row["content"] if row else None

    def document_chunks(self, document_id: str,
                        limit: int = 500) -> List[Dict[str, Any]]:
        """Textes des chunks d'un ouvrage, ordre stable (comparaison)."""
        rows = self._conn.execute(
            "SELECT id, text FROM chunks WHERE document_id=? ORDER BY id"
            " LIMIT ?", (document_id, limit)).fetchall()
        return [dict(r) for r in rows]
