"""Wilfrid — acquisition P6.2 : téléchargement + parsing pilotés par jobs.

Utilise les contrats P6.1 sans les modifier : transitions
QUEUED→DOWNLOADING→PARSING→état final, checkpoints persistants
(`downloaded`, `parsed-<doc_id>`), reprise idempotente.
Zone temporaire/quarantaine distincte du corpus validé : les fichiers
partiels vivent en `<base>/tmp`, seuls les documents validés vont
en `<base>/corpus`. Aucun document partiel n'est un document valide.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from core.knowledge import downloader as _download
from core.knowledge import parsers as _parsers
from core.knowledge.jobs import JobManager
from core.knowledge.store import KnowledgeStore


def acquire_and_parse(job_id: str, url: str, filename: str, *,
                      jobs: JobManager, store: KnowledgeStore,
                      check_permission, check_whitelist, log=None,
                      base_dir: str | Path,
                      expected_sha256: str = "",
                      limits=None) -> Dict[str, Any]:
    """Exécute acquisition + parsing pour un job (états P6.1 intacts)."""
    base = Path(base_dir)
    tmp_dir = base / "tmp"
    corpus_dir = base / "corpus"
    job = jobs.transition(job_id, "DOWNLOADING")
    _ = job
    result = _download.download(
        url, tmp_dir, filename,
        check_permission=check_permission,
        check_whitelist=check_whitelist,
        log=log, job_id=job_id, limits=limits or _download.DownloadLimits(),
        expected_sha256=expected_sha256, resume=True,
    )
    if not result.ok or result.path is None:
        jobs.transition(job_id, "FAILED")
        return {"ok": False, "stage": "download", "error": result.error}
    jobs.complete_step(job_id, "downloaded")
    jobs.transition(job_id, "PARSING")
    try:
        parsed = _parsers.parse_document(result.path, result.mime_declared)
    except _parsers.ParseError as exc:
        try:
            result.path.unlink(missing_ok=True)
        except OSError:
            pass
        jobs.transition(job_id, "FAILED")
        return {"ok": False, "stage": "parse", "error": str(exc)[:200]}
    doc_id = f"doc-{result.sha256[:16]}"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    final_path = corpus_dir / (doc_id + Path(filename).suffix.lower())
    try:
        if final_path.is_file():
            result.path.unlink(missing_ok=True)  # doublon SHA : dédupliqué
        else:
            result.path.replace(final_path)
    except OSError as exc:
        jobs.transition(job_id, "FAILED")
        return {"ok": False, "stage": "store", "error": str(exc)[:200]}
    store.upsert_document(doc_id, result.sha256, title=parsed["meta"].get(
        "title", ""), author=parsed["meta"].get("author", ""),
        status="PARSED" if parsed["status"] == "PARSED" else "NO_TEXT",
        path=str(final_path))
    for page in parsed["pages"]:
        section_id = f"{doc_id}:p{page['n']}"
        try:
            store._conn.execute(
                "INSERT OR IGNORE INTO sections(id, document_id, ordinal,"
                " title) VALUES (?,?,?,?)",
                (section_id, doc_id, page["n"], ""))
        except Exception:
            pass
    store._conn.commit()
    jobs.complete_step(job_id, f"parsed-{doc_id}")
    return {"ok": True, "stage": "parsed", "doc_id": doc_id,
            "sha256": result.sha256, "size": result.size,
            "status": parsed["status"],
            "pages": len(parsed["pages"]),
            "chars": parsed["meta"].get("chars", 0)}
