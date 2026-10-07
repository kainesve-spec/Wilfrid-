"""Wilfrid — environnement externe gouverné O7 (fetch HTTPS borné, sans exécution).

Couche de politique + orchestration DEVANT le downloader P6.2 existant
(réutilisé tel quel, aucune infrastructure réseau parallèle) :
requête explicite → permission DOCUMENT_DOWNLOAD → garde SSRF (IP
littérales non publiques refusées, sans socket ici) → whitelist exacte →
téléchargement borné → provenance + UNTRUSTED DATA. Aucune décision
d'autorité créée : capacité technique ≠ permission, et seule une URL
explicite est traitée (jamais devinée). Contenu externe = donnée inerte.
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.knowledge import downloader as _download

FETCH_STATUSES = (
    "ALLOWED", "DENIED", "DEFERRED", "AMBIGUOUS", "TIMEOUT", "BLOCKED",
    "INVALID", "FETCHED", "PARTIAL", "FAILED", "UNTRUSTED",
)

_DEFAULT_SCHEMES = ("https",)


@dataclass(frozen=True)
class ExternalPolicy:
    """Bornes choisies pour le fetch gouverné (défauts documentés, pas universels)."""

    max_bytes: int = 5 * 1024 * 1024
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 15.0
    max_redirects: int = 3
    schemes: Tuple[str, ...] = _DEFAULT_SCHEMES
    allow_private_ips: bool = False
    allowed_mime: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class ExternalRequest:
    """Demande explicite : URL fournie, jamais devinée ni découverte seule."""

    url: str = ""
    job_id: str = ""


@dataclass(frozen=True)
class ExternalSource:
    """Source résolue : hôte exact + entrée whitelist correspondante."""

    host: str = ""
    port: int = 443
    entry_limits: Tuple[Tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class ExternalAccessDecision:
    """Décision pré-accès : ALLOWED / DENIED / DEFERRED / AMBIGUOUS / INVALID."""

    decision: str = "DENIED"
    reason: str = ""
    source: Optional[ExternalSource] = None


@dataclass(frozen=True)
class ExternalProvenance:
    """Provenance factuelle : jamais inventée, confiance non affirmée."""

    source: str = ""
    location: str = ""
    retrieved_at: float = 0.0
    acquired_at: float = 0.0
    content_type: str = ""
    extraction_status: str = "not-parsed"
    confidence: str = "unverified"
    sha256: str = ""
    size: int = 0


@dataclass(frozen=True)
class ExternalFetchResult:
    """Résultat : statut fermé + données inertes + provenance."""

    status: str = "FAILED"
    untrusted: bool = True
    decision: str = "DENY"
    path: Optional[str] = None
    provenance: Optional[ExternalProvenance] = None
    reason: str = ""


def _valid_policy(policy: Any) -> Tuple[bool, str]:
    """Politique bien formée : https seul, bornes strictement positives."""
    if not isinstance(policy, ExternalPolicy):
        return False, "politique-invalide"
    if not isinstance(policy.schemes, tuple) or not policy.schemes \
            or any(s != "https" for s in policy.schemes):
        return False, "protocole-non-supporte"
    value = policy.max_bytes
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return False, "borne-invalide:max_bytes"
    for field_name in ("connect_timeout_s", "read_timeout_s"):
        value = getattr(policy, field_name)
        if not isinstance(value, (int, float)) \
                or isinstance(value, bool) or float(value) <= 0.0:
            return False, f"borne-invalide:{field_name}"
    if not isinstance(policy.max_redirects, int) \
            or isinstance(policy.max_redirects, bool) \
            or not 0 <= policy.max_redirects <= 10:
        return False, "borne-invalide:max_redirects"
    if policy.allowed_mime is not None and not (
            isinstance(policy.allowed_mime, tuple)
            and all(isinstance(m, str) and m for m in policy.allowed_mime)):
        return False, "borne-invalide:allowed_mime"
    if not isinstance(policy.allow_private_ips, bool):
        return False, "borne-invalide:allow_private_ips"
    return True, "ok"


def _split_url(url: Any) -> Tuple[bool, str, str, int, str]:
    """Découpe stricte https://host[:port][/path] sans urllib (banni ici).

    Retourne (ok, scheme, host, port, reason). Aucune normalisation
    permissive : userinfo, port invalide, hôte vide = rejet.
    """
    if not isinstance(url, str):
        return False, "", "", 0, "url-invalide"
    text = url.strip()
    if "://" not in text:
        return False, "", "", 0, "url-invalide"
    scheme, _, rest = text.partition("://")
    scheme = scheme.lower()
    if "/" in rest:
        authority, _, _path = rest.partition("/")
    else:
        authority, _path = rest, ""
    if "@" in authority or not authority:
        return False, "", "", 0, "url-invalide"
    if authority.startswith("["):
        end = authority.find("]")
        if end < 0:
            return False, "", "", 0, "url-invalide"
        host, tail = authority[1:end], authority[end + 1:]
        if tail and not tail.startswith(":"):
            return False, "", "", 0, "url-invalide"
        port_text = tail[1:] if tail else ""
    elif authority.count(":") > 1:
        return False, "", "", 0, "url-invalide"
    else:
        host, _, port_text = authority.partition(":")
    host = host.strip().lower().rstrip(".")
    if not host:
        return False, "", "", 0, "url-invalide"
    if port_text:
        if not port_text.isdigit():
            return False, "", "", 0, "port-invalide"
        port = int(port_text)
        if not 1 <= port <= 65535:
            return False, "", "", 0, "port-invalide"
    else:
        port = 443 if scheme == "https" else 80
    return True, scheme, host, port, "ok"


def _ip_blocked_reason(host: str) -> Optional[str]:
    """IP littérales non publiques = BLOCKED (SSRF direct, sans socket)."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return None
    if addr.is_loopback:
        return "ssrf-loopback"
    if addr.is_link_local:
        return "ssrf-link-local"
    if addr.is_multicast:
        return "ssrf-multicast"
    if getattr(addr, "is_reserved", False):
        return "ssrf-reserved"
    if addr.is_private:
        return "ssrf-prive"
    if addr.is_unspecified:
        return "ssrf-unspecified"
    return None


def _entry_limits(check_whitelist: Callable, host: str) -> Optional[Dict[str, Any]]:
    """Limites de l'entrée whitelist exacte, si exposées (comparaison redirects)."""
    try:
        entries = check_whitelist.__self__.entries()  # type: ignore[union-attr]
    except Exception:
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("domain") == host:
            limits = entry.get("limits")
            if isinstance(limits, dict):
                return dict(limits)
            return {}
    return None


def decide_access(url: Any, *, check_permission: Callable,
                  check_whitelist: Callable,
                  policy: Optional[ExternalPolicy] = None,
                  ) -> ExternalAccessDecision:
    """Pré-accès : permission → politique → whitelist. Aucun I/O réseau."""
    policy = policy or ExternalPolicy()
    policy_ok, policy_why = _valid_policy(policy)
    if not policy_ok:
        return ExternalAccessDecision("INVALID", policy_why, None)
    ok, scheme, host, port, reason = _split_url(url)
    if not ok:
        return ExternalAccessDecision("INVALID", reason, None)
    if scheme != "https":
        return ExternalAccessDecision("INVALID", "protocole-non-supporte",
                                      None)
    ip_reason = _ip_blocked_reason(host)
    if ip_reason is not None and not policy.allow_private_ips:
        return ExternalAccessDecision("BLOCKED", ip_reason, None)
    try:
        allowed, perm_reason = check_permission("DOCUMENT_DOWNLOAD", url)
    except Exception as exc:
        return ExternalAccessDecision("DENIED", f"permission-erreur:{type(exc).__name__}",
                                      None)
    if not allowed:
        if perm_reason in ("disabled", "unknown-permission", "permission-inconnue"):
            return ExternalAccessDecision("DEFERRED", f"permission:{perm_reason}",
                                          None)
        return ExternalAccessDecision("DENIED", f"permission:{perm_reason}",
                                      None)
    try:
        wl_ok, wl_reason = check_whitelist(url)
    except Exception as exc:
        return ExternalAccessDecision("DENIED", f"whitelist-erreur:{type(exc).__name__}",
                                      None)
    if not wl_ok:
        return ExternalAccessDecision("DENIED", f"whitelist:{wl_reason}", None)
    limits = _entry_limits(check_whitelist, host)
    source = ExternalSource(host=host, port=port,
                            entry_limits=tuple(sorted((limits or {}).items())))
    return ExternalAccessDecision("ALLOWED", "controles-ok", source)


def _recording_checker(check_whitelist: Callable,
                       visited: List[str]) -> Callable:
    def wrapper(url: str) -> Tuple[bool, str]:
        visited.append(url)
        return check_whitelist(url)
    return wrapper


def _limits_of(host: str, check_whitelist: Callable) -> Optional[Dict[str, Any]]:
    try:
        entries = check_whitelist.__self__.entries()  # type: ignore[union-attr]
    except Exception:
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("domain") == host:
            limits = entry.get("limits")
            return dict(limits) if isinstance(limits, dict) else {}
    return None


def _check_redirect_chain(original_host: str, visited: List[str],
                           check_whitelist: Callable) -> Optional[str]:
    """Conflit de limites entre hôtes visités → AMBIGUOUS (fail-closed)."""
    ref: Optional[Dict[str, Any]] = None
    for raw in visited:
        ok, _, host, _, _ = _split_url(raw)
        if not ok or host == original_host:
            continue
        other = _limits_of(host, check_whitelist)
        if ref is None:
            ref = _limits_of(original_host, check_whitelist)
        if other != ref:
            return f"limites-divergentes:{host}"
    return None


def fetch(url: Any, dest_dir: Any, filename: Any, *,
          check_permission: Callable, check_whitelist: Callable,
          policy: Optional[ExternalPolicy] = None,
          log: Any = None, job_id: str = "") -> ExternalFetchResult:
    """Fetch HTTPS gouverné : politique puis downloader P6.2 existant."""
    policy = policy or ExternalPolicy()
    decision = decide_access(url, check_permission=check_permission,
                             check_whitelist=check_whitelist, policy=policy)
    if decision.decision != "ALLOWED" or decision.source is None:
        status = {"INVALID": "INVALID", "DENIED": "DENIED",
                  "DEFERRED": "DEFERRED", "BLOCKED": "BLOCKED"}.get(
                      decision.decision, "DENIED")
        if log is not None:
            try:
                log(action="external.decide", permission_id="DOCUMENT_DOWNLOAD",
                    decision="DENY", reason=decision.reason, target=str(url),
                    job_id=job_id)
            except Exception:
                pass
        return ExternalFetchResult(status=status, decision="DENY",
                                   reason=decision.reason)
    if not isinstance(filename, str) or not filename.strip() \
            or len(filename) > 128:
        return ExternalFetchResult(status="INVALID", decision="DENY",
                                   reason="nom-fichier-invalide")
    safe_name = "".join(c if (c.isalnum() or c in ("-", "_", ".")) else "_"
                        for c in filename.strip())[:128]
    if not safe_name or safe_name in (".", ".."):
        return ExternalFetchResult(status="INVALID", decision="DENY",
                                   reason="nom-fichier-invalide")
    visited: List[str] = []
    recording = _recording_checker(check_whitelist, visited)
    limits = _download.DownloadLimits(
        max_bytes=policy.max_bytes,
        connect_timeout_s=policy.connect_timeout_s,
        read_timeout_s=policy.read_timeout_s,
        max_redirects=policy.max_redirects)
    try:
        result = _download.download(
            url, dest_dir, safe_name, check_permission=check_permission,
            check_whitelist=recording, log=log, job_id=job_id, limits=limits)
    except Exception as exc:
        return ExternalFetchResult(status="FAILED", decision="DENY",
                                   reason=f"fetch-exception:{type(exc).__name__}")
    if not result.ok:
        error = result.error or ""
        if error.startswith("TIMEOUT"):
            status = "TIMEOUT"
        elif error.startswith("DENIED"):
            status = "DENIED"
        else:
            status = "FAILED"
        return ExternalFetchResult(status=status, decision="DENY",
                                   reason=error[:200])
    conflict = _check_redirect_chain(decision.source.host, visited,
                                     check_whitelist)
    if conflict is not None:
        try:
            Path(result.path).unlink(missing_ok=True)
        except OSError:
            pass
        return ExternalFetchResult(status="AMBIGUOUS", decision="DENY",
                                   reason=conflict)
    if policy.allowed_mime is not None:
        mime = (result.mime_declared or "").lower()
        if not any(mime.startswith(str(prefix).lower())
                   for prefix in policy.allowed_mime):
            try:
                Path(result.path).unlink(missing_ok=True)
            except OSError:
                pass
            return ExternalFetchResult(status="BLOCKED", decision="DENY",
                                       reason="mime-non-autorise")
    retrieved = time.time()
    provenance = ExternalProvenance(
        source=decision.source.host, location=result.url_final,
        retrieved_at=retrieved, acquired_at=retrieved,
        content_type=result.mime_declared, extraction_status="not-parsed",
        confidence="unverified", sha256=result.sha256, size=result.size)
    return ExternalFetchResult(status="FETCHED", decision="ALLOW",
                               path=str(result.path), provenance=provenance,
                               reason="ok")
