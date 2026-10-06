"""Wilfrid — résolveur jail P7 C2 (confinement centralisé, sans effet).

Garantit : racine canonique, cible strictement descendante, rejet `..`,
absolu-hors-jail, symlink (tout suivi refusé), ambiguïté, hors-jail,
secrets/.env, profondeur 1..3 depuis JAIL/P7. Jamais de simple préfixe
textuel comme unique protection : canonisation + parents réels + double
lstat + revérification post-open par l'appelant. Lecture seule ici
(aucune écriture, aucune création sauf `ensure_jail`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from core.p7 import errors as E
from core.p7.types import target_in_scope, validate_scope_format

MAX_DEPTH = 3

_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_RESERVED = {".backup", ".tmp", "notifications"}
_SECRET_HINTS = ("secret", "credential", "token", "passwd")


def jail_root() -> Path:
    """Racine validée B3 : <repo>/JAIL/P7 (absolue, lexicale)."""
    repo = Path(__file__).resolve().parents[2]
    return repo / "JAIL" / "P7"


def is_jail_present() -> bool:
    try:
        root = jail_root()
    except OSError:
        return False
    return root.is_dir() and not root.is_symlink()


def ensure_jail() -> Tuple[bool, str, Optional[Path]]:
    """Crée la racine avec permissions raisonnables (0o700), sans autorité root."""
    root = jail_root()
    try:
        if root.is_symlink():
            return False, E.SCOPE_NOT_COVERING, None
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not root.is_dir() or root.is_symlink():
            return False, E.SCOPE_NOT_COVERING, None
    except OSError as exc:
        return False, f"{E.UNKNOWN_ERROR}:{type(exc).__name__}", None
    return True, "ok", root


def _deny(reason: str) -> Tuple[bool, str, None]:
    return False, reason, None


def _component_ok(comp: str, resource: str = "fichier") -> Tuple[bool, str]:
    if not comp or comp in (".", ".."):
        return False, E.SCOPE_NOT_COVERING
    if comp in {".backup", ".tmp"} or comp == ".env":
        return False, E.SCOPE_NOT_COVERING
    if comp == "notifications" and resource != "notification":
        return False, E.SCOPE_NOT_COVERING
    lowered = comp.lower()
    if any(h in lowered for h in _SECRET_HINTS):
        return False, E.SCOPE_NOT_COVERING
    if "\\" in comp or comp != comp.strip():
        return False, E.SCOPE_NOT_COVERING
    if _COMPONENT_RE.match(comp) is None:
        return False, E.SCOPE_NOT_COVERING
    return True, "ok"


def _symlink_free_chain(root_canon: Path, candidate: Path) -> bool:
    """Tout maillon existant symlinké (fichier cible inclus) = échec."""
    try:
        rel = candidate.relative_to(root_canon)
    except ValueError:
        return False
    node = root_canon
    if node.is_symlink():
        return False
    for part in rel.parts:
        node = node / part
        try:
            if node.is_symlink():
                return False
        except OSError:
            return False
    return True


def resolve(scope: str, target: str) -> Tuple[bool, str, Optional[Path]]:
    """Confine `target` (== périmètre du scope) sous la racine. Zéro mutation."""
    ok, why = validate_scope_format(scope)
    if not ok:
        return _deny(E.SCOPE_INVALID)
    covered, _ = target_in_scope(scope, target)
    if not covered:
        return _deny(E.SCOPE_NOT_COVERING)
    raw = str(target)
    if not raw or len(raw) > 512:
        return _deny(E.SCOPE_NOT_COVERING)
    for banned in ("*", "\n", "\r", "\x00"):
        if banned in raw:
            return _deny(E.SCOPE_NOT_COVERING)
    root_lex = jail_root()
    if raw.startswith("~/"):
        prefix = "~/Wilfrid/JAIL/P7/"
        if not raw.startswith(prefix):
            return _deny(E.SCOPE_NOT_COVERING)
        rel_lex = raw[len(prefix):]
    elif raw.startswith("/"):
        try:
            rel_lex = str(Path(raw).relative_to(root_lex))
        except ValueError:
            return _deny(E.SCOPE_NOT_COVERING)
    else:
        if raw.startswith("./") or "/./" in raw or raw.endswith("/."):
            return _deny(E.SCOPE_NOT_COVERING)
        rel_lex = raw
    if not rel_lex or rel_lex.startswith("/") or rel_lex.endswith("/"):
        return _deny(E.SCOPE_NOT_COVERING)
    parts = rel_lex.split("/")
    if len(parts) < 1 or len(parts) > MAX_DEPTH:
        return _deny(E.LIMITS_INVALID)
    resource = str(scope).split(":")[0].strip()
    for comp in parts:
        good, _ = _component_ok(comp, resource)
        if not good:
            return _deny(E.SCOPE_NOT_COVERING)
    node = root_lex
    try:
        if node.is_symlink():
            return _deny(E.SCOPE_NOT_COVERING)
        for comp in parts:
            node = node / comp
            if node.is_symlink():
                return _deny(E.SCOPE_NOT_COVERING)
            if "\\" in comp:
                return _deny(E.SCOPE_NOT_COVERING)
    except OSError:
        return _deny(E.SCOPE_NOT_COVERING)
    try:
        root_canon = root_lex.resolve()
        canon = (root_lex.joinpath(*parts)).resolve(strict=False)
    except OSError:
        return _deny(E.SCOPE_NOT_COVERING)
    if canon == root_canon:
        return _deny(E.SCOPE_NOT_COVERING)
    try:
        rel = canon.relative_to(root_canon)
    except ValueError:
        return _deny(E.SCOPE_NOT_COVERING)
    if len(rel.parts) < 1 or len(rel.parts) > MAX_DEPTH:
        return _deny(E.LIMITS_INVALID)
    for comp in rel.parts:
        good, _ = _component_ok(comp, resource)
        if not good:
            return _deny(E.SCOPE_NOT_COVERING)
    if not _symlink_free_chain(root_canon, canon):
        return _deny(E.SCOPE_NOT_COVERING)
    return True, "ok", canon


def confined_path(scope: str, target: str) -> Tuple[bool, str, Optional[Path]]:
    """Alias sémantique : synonyme de `resolve` pour les appelants."""
    return resolve(scope, target)
