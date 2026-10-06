"""Wilfrid — écriture réversible P7.JAIL_WRITE_REVERSIBLE (R2).

Ordre : typing→approval→scope→expiry→limits→résolution→capture pré-état→
backup→journal pre-event→write atomique borné→vérification→preuve→journal
post-event. Échec avant écriture : DENY + inchangé. Échec après : restauration
tentée+vérifiée+journalisée ; restauration non vérifiable = FAIL-CLOSED avec
preuve de l'état observé. Single-use en mémoire (1 request_id = 1 acte).
Backups internes `<jail>/.backup/`, jamais cible utilisateur, bornés, liés au
request_id, nettoyables. Aucun réseau, aucun exécutable, aucun secret.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.p7 import errors as E
from core.p7 import governor as G
from core.p7 import resolver as R
from core.p7.journal import Journal
from core.p7.types import Approval, Request

PERMISSION_ID = "P7.JAIL_WRITE_REVERSIBLE"
MAX_FILE_BYTES = 65536
BACKUP_DIRNAME = ".backup"
TMP_SUFFIX = ".tmp"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_CONSUMED: set = set()


def reset_consumed() -> None:
    _CONSUMED.clear()


def _safe_id(request_id: Any) -> Tuple[bool, str]:
    if not isinstance(request_id, str) or SAFE_ID_RE.match(request_id) is None:
        return False, ""
    return True, request_id


def _deny(reason: str, request: Request,
          approval: Optional[Approval]) -> Tuple[G.Decision, None]:
    version = approval.capability_version if isinstance(approval, Approval) else 0
    rid = request.request_id if isinstance(request, Request) else ""
    pid = request.permission_id if isinstance(request, Request) else ""
    return G.Decision(False, reason, G.Proof(rid, pid, "DENY", reason, version,
                                             ("writer",))), None


def _note(journal: Journal, event: str, request: Request,
          approval: Optional[Approval], decision: str, reason: str) -> bool:
    try:
        journal.record(event=event, actor="core",
                       request_id=request.request_id,
                       permission_id=request.permission_id,
                       target=request.target, decision=decision,
                       reason=reason,
                       capability_version=approval.capability_version
                       if isinstance(approval, Approval) else 0,
                       risk="R2")
    except Exception:
        return False
    return True


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _backup_paths(root: Path, safe: str) -> Tuple[Path, Path]:
    directory = root / BACKUP_DIRNAME
    return directory / f"{safe}.bak", directory / f"{safe}.meta.json"


def _remove_backup_files(root: Path, safe: str) -> None:
    bak, meta = _backup_paths(root, safe)
    for path in (bak, meta):
        try:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        except OSError:
            pass


def backup_info(root: Path, request_id: str) -> Dict[str, Any]:
    ok, safe = _safe_id(request_id)
    if not ok:
        return {"present": False, "reason": E.REQUEST_INVALID}
    bak, meta = _backup_paths(root, safe)
    return {"present": bak.is_file() and not bak.is_symlink(),
            "meta_present": meta.is_file() and not meta.is_symlink(),
            "bak": str(bak), "meta": str(meta)}


def cleanup(request_id: str) -> Tuple[bool, str]:
    """Supprime backup/marqueur + tmp résiduels ; vérifie la disparition."""
    ok, safe = _safe_id(request_id)
    if not ok:
        return False, E.REQUEST_INVALID
    root = R.jail_root()
    bak, meta = _backup_paths(root, safe)
    removed = True
    for path in (bak, meta):
        try:
            if path.is_symlink():
                return False, E.SCOPE_NOT_COVERING
            if path.is_file():
                path.unlink()
        except OSError:
            removed = False
    try:
        stray = sorted((root / BACKUP_DIRNAME).glob(f"{safe}.*"))
        leftovers = [p for p in stray if p.name not in (bak.name, meta.name)]
        for path in leftovers:
            try:
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            except OSError:
                removed = False
    except OSError:
        pass
    info = backup_info(root, request_id)
    if info["present"] or info["meta_present"]:
        return False, E.UNKNOWN_ERROR
    return (True, "ok") if removed else (False, E.UNKNOWN_ERROR)


def restore(request: Request) -> Tuple[bool, str]:
    """Restaure depuis le backup vérifié (ou supprime la création)."""
    ok, safe = _safe_id(request.request_id)
    if not ok:
        return False, E.REQUEST_INVALID
    ok_r, _, target = R.resolve(request.scope, request.target)
    if not ok_r or target is None:
        return False, E.SCOPE_NOT_COVERING
    if target.is_symlink():
        return False, E.SCOPE_NOT_COVERING
    root = R.jail_root()
    bak, meta = _backup_paths(root, safe)
    try:
        if bak.is_symlink() or meta.is_symlink():
            return False, E.SCOPE_NOT_COVERING
        if not bak.is_file() or not meta.is_file():
            return False, "BACKUP_MANQUANT"
        meta_doc = json.loads(meta.read_bytes().decode("utf-8"))
        if meta_doc.get("request_id") != request.request_id:
            return False, "BACKUP_CORROMPU"
        blob = bak.read_bytes()
        if _sha(blob) != str(meta_doc.get("sha256", "")):
            return False, "BACKUP_CORROMPU"
        if meta_doc.get("created") is True:
            if target.is_symlink():
                return False, E.SCOPE_NOT_COVERING
            if target.is_file():
                target.unlink()
            if target.exists() or target.is_symlink():
                return False, "RESTAURATION_NON_VÉRIFIÉE"
            return True, "ok"
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = target.parent / f".tmp.restore.{safe}"
        tmp.write_bytes(blob)
        tmp.replace(target)
        check = target.read_bytes()
        if _sha(check) != str(meta_doc.get("sha256", "")):
            return False, "RESTAURATION_NON_VÉRIFIÉE"
        return True, "ok"
    except (OSError, ValueError, KeyError):
        return False, "RESTAURATION_NON_VÉRIFIÉE"


def write_one(request: Request, approval: Optional[Approval],
              now: float, journal: Journal, data: bytes) -> Tuple[G.Decision, Optional[Dict[str, Any]]]:
    """Écrit 1 fichier borné avec backup obligatoire. Single-use."""
    t0 = time.monotonic()
    if not isinstance(data, (bytes, bytearray)):
        return _deny(E.LIMITS_INVALID, request, approval)
    payload = bytes(data)
    decision = G.decide(request, approval, now, journal.available())
    if not decision.allowed:
        return decision, None
    if request.permission_id != PERMISSION_ID:
        return _deny(E.PERMISSION_UNKNOWN, request, approval)
    if request.request_id in _CONSUMED:
        return _deny("SECONDE_ACTION", request, approval)
    timeout_s = request.limits.get("timeout_s", 0)
    if not isinstance(timeout_s, int) or isinstance(timeout_s, bool):
        return _deny(E.LIMITS_INVALID, request, approval)
    if timeout_s < 1 or timeout_s > 5:
        return _deny(E.LIMITS_INVALID, request, approval)
    if len(payload) > MAX_FILE_BYTES:
        return _deny(E.LIMITS_INVALID, request, approval)
    ok_id, safe = _safe_id(request.request_id)
    if not ok_id:
        return _deny(E.REQUEST_INVALID, request, approval)
    ok_j, _, root = R.ensure_jail()
    if not ok_j or root is None:
        return _deny(E.UNKNOWN_ERROR, request, approval)
    ok_r, why_r, target = R.resolve(request.scope, request.target)
    if not ok_r or target is None:
        return _deny(why_r, request, approval)
    if not journal.available():
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    try:
        pre_exists = target.is_file() and not target.is_symlink()
        if target.is_symlink():
            return _deny(E.SCOPE_NOT_COVERING, request, approval)
        pre_bytes = target.read_bytes() if pre_exists else b""
        if pre_exists and len(pre_bytes) > MAX_FILE_BYTES:
            return _deny(E.LIMITS_INVALID, request, approval)
    except OSError:
        return _deny(E.UNKNOWN_ERROR, request, approval)
    backup_dir = root / BACKUP_DIRNAME
    try:
        if backup_dir.is_symlink():
            return _deny(E.SCOPE_NOT_COVERING, request, approval)
        backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return _deny("BACKUP_IMPOSSIBLE", request, approval)
    bak, meta = _backup_paths(root, safe)
    try:
        if pre_exists:
            if bak.is_symlink() or meta.is_symlink():
                return _deny(E.SCOPE_NOT_COVERING, request, approval)
            bak.write_bytes(pre_bytes)
            meta.write_text(json.dumps({"request_id": request.request_id,
                                        "sha256": _sha(pre_bytes),
                                        "size": len(pre_bytes),
                                        "created": False}), encoding="utf-8")
            if _sha(bak.read_bytes()) != _sha(pre_bytes):
                return _deny("BACKUP_IMPOSSIBLE", request, approval)
        else:
            bak.write_bytes(b"")
            meta.write_text(json.dumps({"request_id": request.request_id,
                                        "sha256": _sha(b""),
                                        "size": 0,
                                        "created": True}), encoding="utf-8")
    except OSError:
        return _deny("BACKUP_IMPOSSIBLE", request, approval)
    if not _note(journal, "pre-write", request, approval, "ALLOW", "ok"):
        try:
            bak.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
        except OSError:
            pass
        return _deny(E.JOURNAL_UNAVAILABLE, request, approval)
    try:
        ok_r2, _, target2 = R.resolve(request.scope, request.target)
        if not ok_r2 or target2 is None or target2 != target:
            raise OSError("target-changed")
        target2.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = target2.parent / f".tmp.{safe}"
        if tmp.is_symlink():
            raise OSError("tmp-symlink")
        tmp.write_bytes(payload)
        tmp.replace(target2)
    except OSError as exc:
        restored, why_restore = restore(request)
        _note(journal, "error", request, approval, "DENY",
              f"WRITE_FAIL:{why_restore}")
        if restored:
            _remove_backup_files(root, safe)
        return _deny(f"WRITE_FAIL:{type(exc).__name__}", request, approval)
    try:
        if target.is_symlink() or not target.is_file():
            raise OSError("post-missing")
        observed = target.read_bytes()
        if observed != payload:
            raise OSError("post-mismatch")
    except OSError:
        restored, why_restore = restore(request)
        _note(journal, "error", request, approval, "DENY",
              f"POST_FAIL:restored={restored}:{why_restore}")
        if not restored:
            detail = {"observed_size": -1, "restored": False,
                      "restore_reason": why_restore,
                      "backup": str(bak)}
            version = approval.capability_version if isinstance(approval, Approval) else 0
            fail = G.Decision(False, "RESTAURATION_NON_VÉRIFIÉE", G.Proof(
                request.request_id, request.permission_id, "DENY",
                "RESTAURATION_NON_VÉRIFIÉE", version, ("writer",)))
            return fail, detail
        _remove_backup_files(root, safe)
        return _deny("POST_FAIL:restored", request, approval)
    if time.monotonic() - t0 > timeout_s:
        restored, why_restore = restore(request)
        _note(journal, "error", request, approval, "DENY",
              f"TIMEOUT:restored={restored}:{why_restore}")
        if restored:
            _remove_backup_files(root, safe)
        return _deny(E.LIMITS_INVALID, request, approval)
    _CONSUMED.add(request.request_id)
    _note(journal, "post-write", request, approval, "ALLOW", "ok")
    return decision, {"target": str(target), "bytes": len(payload),
                      "sha256": _sha(payload), "backup": str(bak),
                      "restored": False}


def describe() -> Dict[str, Any]:
    return {"id": PERMISSION_ID, "risk": "R2", "max_files": 1,
            "max_file_bytes": MAX_FILE_BYTES, "max_depth": R.MAX_DEPTH,
            "timeout_s": 5, "duration_s": 300, "single_use": True}
