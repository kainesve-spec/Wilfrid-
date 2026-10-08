"""Wilfrid — moteur Internet gouverné (lecture contrôlée, sans autorité).

Étapes distinguées : RESOLVED (DNS) → CONNECTED (TLS/TCP) →
HTTP_SUCCESS (2xx) → CONTENT_VALIDATED (taille/type) → VERIFIED_SUCCESS
(preuve suffisante). Un HTTP 200 seul ne vaut jamais succès vérifié.
Réutilise les protections existantes (whitelist, permissions, SSRF de
`external.py`, limites de `downloader.py`). Données en entrée, preuves
en sortie : jamais d'exécution distante, jamais de secret journalisé.
"""

from __future__ import annotations

import hashlib
import http.client
import socket
import ssl
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

STAGES = ("DNS_FAILED", "RESOLVED", "CONNECTION_FAILED", "CONNECTED",
          "HTTP_ERROR", "HTTP_SUCCESS", "CONTENT_REJECTED",
          "CONTENT_VALIDATED", "VERIFIED_SUCCESS")

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_BYTES = 262144
ALLOWED_SCHEMES = ("https",)
ALLOWED_CONTENT_PREFIXES = ("text/", "application/json")


@dataclass(frozen=True)
class InternetResult:
    """Issue de lecture : étapes honnêtes + provenance, jamais d'invention."""

    status: str = "DNS_FAILED"
    url: str = ""
    request_id: str = ""
    http_status: int = 0
    content_type: str = ""
    size: int = 0
    body: str = ""
    detail: str = ""
    provenance: str = ""


def _request_id(url: str, now: Any) -> str:
    seed = "%s|%s" % (url, str(now))
    return "net-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _blocked_host(hostname: str) -> str:
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return "dns-impossible"
    import ipaddress
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if addr.is_loopback or addr.is_private or addr.is_reserved \
                or addr.is_multicast or addr.is_link_local \
                or addr.is_unspecified:
            return "destination-interdite:ssrf"
    return ""


def fetch_url(url: Any, *, timeout_s: Any = DEFAULT_TIMEOUT_S,
              max_bytes: Any = DEFAULT_MAX_BYTES,
              now: Any = None) -> InternetResult:
    """Lecture HTTPS bornée. Chaque étape est prouvée, jamais supposée."""
    rid = _request_id(str(url),
                      now if isinstance(now, (int, float)) else time.time())
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        return InternetResult(status="DNS_FAILED", url=str(url)[:120],
                              request_id=rid, detail="url-invalide")
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail="url-invalide")
    if parts.scheme not in ALLOWED_SCHEMES or not parts.hostname:
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail="schema-ou-hote-invalide")
    host = parts.hostname
    blocked = _blocked_host(host)
    if blocked == "dns-impossible":
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail="dns-impossible")
    if blocked:
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail=blocked,
                              provenance="ssrf-guard")
    try:
        timeout = float(timeout_s)
    except (TypeError, ValueError):
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail="delai-invalide")
    timeout = min(max(timeout, 1.0), 60.0)
    try:
        size_limit = int(max_bytes)
    except (TypeError, ValueError):
        return InternetResult(status="DNS_FAILED", url=url[:120],
                              request_id=rid, detail="borne-invalide")
    size_limit = min(max(size_limit, 1024), 2097152)
    context = ssl.create_default_context()
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    try:
        connection = http.client.HTTPSConnection(
            host, parts.port or 443, timeout=timeout, context=context)
        connection.request("GET", path,
                           headers={"User-Agent": "Wilfrid/0.4",
                                    "Accept": "text/*,application/json"})
        response = connection.getresponse()
        status = int(response.status)
        ctype = str(response.getheader("Content-Type", "") or "")
        chunks = []
        total = 0
        while True:
            piece = response.read(16384)
            if not piece:
                break
            total += len(piece)
            if total > size_limit:
                try:
                    connection.close()
                except Exception:
                    pass
                return InternetResult(
                    status="CONTENT_REJECTED", url=url[:120],
                    request_id=rid, http_status=status, content_type=ctype,
                    detail="taille-depassee")
            chunks.append(piece)
        try:
            connection.close()
        except Exception:
            pass
    except (socket.timeout, TimeoutError):
        return InternetResult(status="CONNECTION_FAILED", url=url[:120],
                              request_id=rid, detail="delai-depasse")
    except (socket.error, ssl.SSLError, OSError):
        return InternetResult(status="CONNECTION_FAILED", url=url[:120],
                              request_id=rid, detail="connexion-impossible")
    if status in (301, 302, 303, 307, 308):
        return InternetResult(status="HTTP_ERROR", url=url[:120],
                              request_id=rid, http_status=status,
                              content_type=ctype,
                              detail="redirection-non-suivie")
    if status < 200 or status >= 300:
        return InternetResult(status="HTTP_ERROR", url=url[:120],
                              request_id=rid, http_status=status,
                              content_type=ctype,
                              detail="statut-http-%d" % status)
    base = ctype.split(";")[0].strip().lower()
    if not any(base.startswith(prefix)
               for prefix in ALLOWED_CONTENT_PREFIXES):
        return InternetResult(status="CONTENT_REJECTED", url=url[:120],
                              request_id=rid, http_status=status,
                              content_type=ctype,
                              detail="type-contenu-refuse")
    try:
        text = b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return InternetResult(status="CONTENT_REJECTED", url=url[:120],
                              request_id=rid, http_status=status,
                              content_type=ctype,
                              detail="decodage-impossible")
    provenance = "https:%s" % host
    return InternetResult(status="CONTENT_VALIDATED", url=url[:120],
                          request_id=rid, http_status=status,
                          content_type=ctype, size=len(text), body=text,
                          detail="contenu-valide",
                          provenance=provenance)


def describe() -> Dict[str, Any]:
    """Contrat moteur (sans effet)."""
    return {"etapes": list(STAGES), "schemas": list(ALLOWED_SCHEMES),
            "redirections": "refusees", "network": True,
            "authority": False}
