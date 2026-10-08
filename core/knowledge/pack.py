"""Wilfrid — Knowledge Pack local (chargement + ingestion, sans autorité).

Le pack est un répertoire versionné (`manifest.json` + documents texte) :
identité explicite, empreintes SHA-256 vérifiées, ingestion déterministe
et idempotente via le moteur existant (upsert + chunks OR IGNORE +
checkpoints de jobs). Données en entrée, index en sortie : le contenu
n'est jamais interprété comme commande, permission ou mandat.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

MANIFEST_NAME = "manifest.json"
PACK_ID = "wilfrid-core-knowledge"
PACK_VERSION = "1.0.0"
PACK_LANG = "fr"


def pack_dir_default() -> str:
    """Emplacement du pack : répertoire `knowledge_pack/` du dépôt."""
    return str(Path(__file__).resolve().parent.parent.parent /
               "knowledge_pack")


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pack(pack_dir: Any = None) -> Tuple[bool, Any]:
    """Valide le pack : manifeste + fichiers + empreintes. `(ok, ...)`."""
    base = Path(str(pack_dir)) if pack_dir else pack_dir_default()
    manifest_path = base / MANIFEST_NAME
    if not base.is_dir():
        return False, "pack-absent"
    if not manifest_path.is_file():
        return False, "manifeste-absent"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "manifeste-invalide"
    if not isinstance(manifest, dict):
        return False, "manifeste-invalide"
    if manifest.get("pack_id") != PACK_ID:
        return False, "pack-id-inattendu"
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        return False, "documents-absents"
    checked: List[Dict[str, Any]] = []
    for entry in documents:
        if not isinstance(entry, dict):
            return False, "document-invalide"
        for key in ("id", "titre", "categorie", "version", "fichier",
                    "sha256"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                return False, "document-invalide:" + key
        target = base / entry["fichier"]
        if not target.is_file():
            return False, "fichier-absent:" + entry["id"]
        actual = _sha_file(target)
        if actual != entry["sha256"]:
            return False, "empreinte-invalide:" + entry["id"]
        checked.append(entry)
    manifest["documents"] = checked
    return True, manifest


def ingest_pack(store: Any, pack_dir: Any = None,
                manifest: Any = None) -> Tuple[bool, Dict[str, Any]]:
    """Ingère le pack (parse → upsert → chunks). Idempotent, sans doublon.

    Retourne `(ok, stats)` avec documents/chunks/ajoutés/ignorés. Si le
    contenu d'un document a changé (sha différente), ses chunks sont
    remplacés avant réindexation (borné au document).
    """
    base = Path(str(pack_dir)) if pack_dir else Path(pack_dir_default())
    from core.knowledge.parsers import parse_document
    if manifest is None:
        ok, manifest = load_pack(pack_dir)
        if not ok:
            return False, {"raison": manifest}
    stats = {"documents": 0, "chunks": 0, "ajoutes": 0, "ignores": 0,
             "remplaces": 0}
    try:
        for entry in manifest["documents"]:
            doc_id = entry["id"]
            target = base / entry["fichier"]
            try:
                parsed = parse_document(target)
            except Exception:
                return False, {"raison": "analyse-impossible:" + doc_id}
            text = parsed.get("text", "") if isinstance(parsed, dict) \
                else ""
            if not isinstance(text, str) or not text.strip():
                return False, {"raison": "document-vide:" + doc_id}
            sha = _sha_file(target)
            known = store.document_sha(doc_id)
            if known is not None and known != sha:
                store.delete_document_chunks(doc_id)
                stats["remplaces"] += 1
            store.upsert_document(doc_id, sha, title=entry["titre"],
                                  status="ACQUIRED", path=str(target))
            stats["documents"] += 1
            before = store.count_chunks(doc_id)
            job_id = "pack-ingest-%s" % doc_id
            if store.get_job(job_id) is None:
                store.create_job(job_id, "pack-ingest",
                                 document_id=doc_id)
            from core.knowledge import chunking as _chunking
            from core.knowledge.jobs import JobManager
            manager = JobManager(store)
            result = _chunking.index_document_sections(
                store, manager, job_id, doc_id, [(0, text)])
            after = store.count_chunks(doc_id)
            stats["chunks"] += after
            if after > before:
                stats["ajoutes"] += after - before
            else:
                stats["ignores"] += 1
    except Exception:
        return False, {"raison": "ingestion-impossible"}
    return True, stats
