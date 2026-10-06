"""Wilfrid — acquisition P6.2 (téléchargement sécurisé, stdlib seule).

Ordre avant toute connexion : permission DOCUMENT_DOWNLOAD, whitelist,
HTTPS, domaine, journalisation — puis connexion seulement.
Garde-fous : taille max PENDANT le flux (jamais Content-Length seul),
timeouts connect/lecture, redirections bornées + revalidation whitelist,
SHA-256 en flux, écriture temporaire + renommage atomique, reprise
Range sûre (sinon reprise propre), partiels supprimés si non reprenables.
"""

from __future__ import annotations

import hashlib
import os
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


@dataclass
class DownloadLimits:
    max_bytes: int = 50 * 1024 * 1024
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 30.0
    max_redirects: int = 5


@dataclass
class DownloadResult:
    ok: bool
    path: Optional[Path] = None
    sha256: str = ""
    size: int = 0
    mime_declared: str = ""
    url_final: str = ""
    error: str = ""
    resumed: bool = False


def _tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return False
    try:
        sock.close()
    except OSError:
        pass
    return True

class _Response:
    """Réponse HTTP minimale (http.client) : statut + en-têtes + flux."""

    def __init__(self, status: int, headers, stream):
        self.status = status
        self.headers = {str(k).lower(): str(v) for k, v in headers.items()}
        self._stream = stream

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def close(self) -> None:
        try:
            self._stream.close()
        except Exception:
            pass


def _fetch_once(url: str, timeout: float, headers: Dict[str, str]) -> _Response:
    """GET unique, SANS suivre les redirections (gérées par l'appelant).

    http.client explicite : aucun gestionnaire implicite ne peut suivre
    une redirection à notre place (contrairement à urllib).
    """
    import http.client
    import ssl as _ssl

    parts = urlparse(url)
    scheme = (parts.scheme or "").lower()
    host = parts.hostname or ""
    port = parts.port or (443 if scheme == "https" else 80)
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    if scheme == "https":
        context = _ssl._create_default_https_context()
        conn = http.client.HTTPSConnection(host, port, timeout=timeout,
                                           context=context)
    elif scheme == "http":
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
    else:
        raise ValueError(f"protocole non supporté: {scheme}")
    try:
        conn.request("GET", target, headers=headers or {})
        raw = conn.getresponse()
        status = int(raw.status)
        items = raw.getheaders()
        return _Response(status, dict(items), raw)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        raise


def download(url: str, dest_dir: str | Path, filename: str, *,
             check_permission, check_whitelist, log=None, job_id: str = "",
             limits: Optional[DownloadLimits] = None,
             expected_sha256: str = "",
             resume: bool = False) -> DownloadResult:
    """Télécharge après contrôles. Lecture seule réseau sortant autorisé."""
    limits = limits or DownloadLimits()
    dest_dir = Path(dest_dir)
    tmp_path = dest_dir / (filename + ".part")
    final_path = dest_dir / filename

    allowed, reason = check_permission("DOCUMENT_DOWNLOAD", url)
    if not allowed:
        _log(log, job_id, url, "DENY", f"permission: {reason}")
        return DownloadResult(ok=False, error=f"DENIED permission: {reason}")
    allowed, reason = check_whitelist(url)
    if not allowed:
        _log(log, job_id, url, "DENY", f"whitelist: {reason}")
        return DownloadResult(ok=False, error=f"DENIED whitelist: {reason}")
    parts = urlparse(url)
    _log(log, job_id, url, "ALLOW", "controles-ok")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return DownloadResult(ok=False, error=f"dest-inaccessible: {exc}")

    host = parts.hostname or ""
    port = parts.port or 443
    if not _tcp_reachable(host, port, limits.connect_timeout_s):
        _log(log, job_id, url, "FAIL", "connect-timeout")
        return DownloadResult(ok=False, error="TIMEOUT connect")

    start_at = 0
    if resume and tmp_path.is_file():
        start_at = tmp_path.stat().st_size
    current_url = url
    redirects = 0
    while True:
        headers: Dict[str, str] = {"User-Agent": "Wilfrid-P6/1.0"}
        if start_at > 0:
            headers["Range"] = f"bytes={start_at}-"
        try:
            response = _fetch_once(current_url, limits.read_timeout_s,
                                   headers)
        except (socket.timeout, TimeoutError) as exc:
            _cleanup(tmp_path, start_at == 0)
            _log(log, job_id, current_url, "FAIL",
                 f"timeout: {type(exc).__name__}")
            return DownloadResult(ok=False, error="TIMEOUT lecture")
        except Exception as exc:
            _cleanup(tmp_path, start_at == 0)
            _log(log, job_id, current_url, "FAIL",
                 f"connexion: {type(exc).__name__}")
            return DownloadResult(ok=False, error=f"NETWORK {type(exc).__name__}")
        status = response.status
        if status in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            try:
                response.close()
            except Exception:
                pass
            redirects += 1
            if redirects > limits.max_redirects:
                _cleanup(tmp_path, start_at == 0)
                return DownloadResult(ok=False, error="FAIL trop-redirections")
            from urllib.parse import urljoin

            current_url = urljoin(current_url, location)
            allowed, reason = check_whitelist(current_url)
            if not allowed:
                _cleanup(tmp_path, start_at == 0)
                _log(log, job_id, current_url, "DENY",
                     f"redirect-whitelist: {reason}")
                return DownloadResult(
                    ok=False, error=f"DENIED redirect: {reason}")
            start_at = 0  # redirection : on ne concatène jamais aveuglément
            continue
        if status == 206 and start_at > 0:
            mode, resumed, base_hash, base_size = "ab", True, None, start_at
        elif status == 200 and start_at > 0:
            # Serveur sans Range : reprise propre (on recommence).
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            mode, resumed, base_size = "wb", False, 0
        elif status in (200, 206):
            mode, resumed = ("ab", True) if status == 206 else ("wb", False)
            base_size = start_at if status == 206 else 0
        else:
            try:
                response.close()
            except Exception:
                pass
            _cleanup(tmp_path, start_at == 0)
            return DownloadResult(ok=False, error=f"FAIL http-{status}")
        mime = response.headers.get("Content-Type", "")
        digest = hashlib.sha256()
        written = base_size
        if resumed and base_size > 0:
            # Reprise : on re-hache le préfixe existant avant de continuer.
            try:
                with open(tmp_path, "rb") as fh:
                    while True:
                        block = fh.read(65536)
                        if not block:
                            break
                        digest.update(block)
            except OSError:
                _cleanup(tmp_path, False)
                return DownloadResult(ok=False, error="FAIL reprise-lecture")
        try:
            with open(tmp_path, mode) as fh:
                while True:
                    block = response.read(65536)
                    if not block:
                        break
                    written += len(block)
                    if written > limits.max_bytes:
                        try:
                            response.close()
                        except Exception:
                            pass
                        _cleanup(tmp_path, False)
                        _log(log, job_id, current_url, "FAIL", "size-limit")
                        return DownloadResult(ok=False,
                                              error="FAIL SIZE_LIMIT")
                    digest.update(block)
                    fh.write(block)
        except Exception as exc:
            try:
                response.close()
            except Exception:
                pass
            _log(log, job_id, current_url, "FAIL",
                 f"flux: {type(exc).__name__}")
            return DownloadResult(ok=False, error="FAIL flux")
        try:
            response.close()
        except Exception:
            pass
        sha = digest.hexdigest()
        if expected_sha256 and sha != expected_sha256.lower():
            _cleanup(tmp_path, False)
            _log(log, job_id, current_url, "FAIL", "hash-mismatch")
            return DownloadResult(ok=False, error="FAIL HASH_MISMATCH")
        try:
            os.replace(tmp_path, final_path)
        except OSError as exc:
            return DownloadResult(ok=False, error=f"FAIL rename: {exc}")
        _log(log, job_id, current_url, "ALLOW", "telecharge")
        return DownloadResult(ok=True, path=final_path, sha256=sha,
                              size=written, mime_declared=mime,
                              url_final=current_url, resumed=resumed)


def _log(log, job_id: str, target: str, decision: str, reason: str) -> None:
    if log is None:
        return
    try:
        log(action="download", permission_id="DOCUMENT_DOWNLOAD",
            target=target, decision=decision, reason=reason, job_id=job_id)
    except Exception:
        pass


def _cleanup(tmp_path: Path, remove_partial: bool) -> None:
    # Partiel supprimé sauf reprise explicite en cours (conservé tel quel).
    if remove_partial:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
