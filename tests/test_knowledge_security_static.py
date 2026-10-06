"""Tests P6.6 — sécurité statique : AST de tout core/knowledge."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = PROJECT_ROOT / "core" / "knowledge"

BANNED_IMPORTS = {"subprocess", "socket", "requests", "httpx", "urllib",
                  "ftplib", "webbrowser", "os", "sys", "sqlite3",
                  "ctypes", "pty", "signal", "multiprocessing"}


def _trees():
    out = []
    for path in sorted(KNOWLEDGE.glob("*.py")):
        out.append((path.name, ast.parse(path.read_text(encoding="utf-8"))))
    return out


def test_no_dangerous_imports():
    """Aucun import réseau/shell/système, sauf usages P6.2 justifiés.

    downloader.py (P6.2, inchangé) utilise socket (TCP reachability +
    http.client) et urllib.parse (parsing pur) : vérifié et hors scope.
    """
    for name, tree in _trees():
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        banned = (mods & BANNED_IMPORTS) - {"sqlite3"}
        if name in ("downloader.py", "whitelist.py"):
            # P6.1/P6.2 audités : socket + urllib.parse (downloader, TCP +
            # parsing pur) et urllib.parse seul (whitelist) ; stdlib xml/zip
            # pour parsers (pas de résolution externe, voir tests XXE).
            banned -= {"socket", "urllib", "os", "xml"}
        assert not banned, f"{name}: {sorted(banned)}"
        if "sqlite3" in mods:
            assert name == "store.py", name


def test_no_dynamic_execution():
    """Ni eval/exec ni chargement dynamique dans core/knowledge."""
    for name, tree in _trees():
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
        assert not (calls & {"eval", "exec", "compile", "__import__",
                             "system", "popen"}), f"{name}: {calls}"


def test_no_taios_qanxorus_network_strings():
    # URIs de namespaces XML (http://...) dans formats.py : identifiants,
    # jamais accédés (vérifié : aucun client HTTP/socket hors downloader).
    for name, tree in _trees():
        src = ast.dump(tree)
        for token in ("TAIOS", "QanXorus", "Binance", "localhost",
                      "127.0.0.1"):
            assert token not in src, f"{name}: {token}"
    import re

    text = "\n".join(
        (PROJECT_ROOT / "core" / "knowledge" / name).read_text(
            encoding="utf-8")
        for name, _ in _trees())
    assert "urlopen" not in text and "urlretrieve" not in text


def test_permissions_explicit_by_construction():
    import core.knowledge.permissions as perms

    assert set(perms.PERMISSION_IDS) == {
        "INTERNET_RESEARCH", "SOURCE_ACCESS", "DOCUMENT_DOWNLOAD",
        "DOCUMENT_PERSIST", "KNOWLEDGE_WRITE", "KNOWLEDGE_UPDATE",
        "CROSS_DOCUMENT_ANALYSIS", "NOTIFY_COMPLETION"}
    assert len(perms.PERMISSION_IDS) == 8
