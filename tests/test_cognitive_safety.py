"""Tests P5 — sécurité statique + non-régression (lecture seule projet)."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_FORBIDDEN_IMPORTS = {
    "subprocess", "socket", "requests", "httpx", "urllib", "webbrowser",
    "sqlite3", "elevenlabs", "sounddevice", "onnxruntime",
}

P1_PINS = {
    "models/wake.onnx":
        "87eead450ef6c2964229f40c936dc03d205dd0bb3d63c33806e8f5a68fa6d333",
    "models/wake.json":
        "c8c62f8b2358e4bdb74149eebfd992f4dbc6d15b13527c24fa42b7169dc09e06",
    "tools/score_wavs.py":
        "269ba8d1adf1e051e39be1f00476ef2e5860f1cef63ace26d6b19394dcd64dd9",
    "tests/test_wake_harness.py":
        "7a09c6a27cfc35ab0bd4ee33a19366c6068f9cbebf65ad56bc6f0dbace6ea272",
}


def _cognitive_files():
    return sorted((PROJECT_ROOT / "core" / "cognitive").glob("*.py"))


def test_no_forbidden_imports():
    """Aucune capacité d'action/réseau/IA importée par core/cognitive/."""
    assert _cognitive_files(), "module P5 absent"
    for path in _cognitive_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & _FORBIDDEN_IMPORTS), f"{path.name}: {imported}"


def _code_without_docstrings(path: Path) -> ast.Module:
    """AST dont les docstrings sont neutralisées (code seul audité)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body[0].value.value = ""
    return tree


def test_no_system_level_calls():
    """Aucun appel système/réseau/fichier sensible dans le code P5."""
    for path in _cognitive_files():
        tree = _code_without_docstrings(path)
        mods: set[str] = set()
        dangerous: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(
                        func.value, ast.Name):
                    if func.value.id in ("os", "sys", "subprocess", "socket",
                                         "requests", "httpx", "urllib",
                                         "webbrowser", "sqlite3", "pathlib",
                                         "shutil"):
                        dangerous.add(f"{func.value.id}.{func.attr}")
                elif isinstance(func, ast.Name):
                    if func.id in ("open", "exec", "eval", "compile",
                                   "__import__", "input"):
                        dangerous.add(func.id)
        assert not (mods & {"subprocess", "socket", "requests", "httpx",
                            "urllib", "webbrowser", "sqlite3"}), path.name
        assert not dangerous, f"{path.name}: {sorted(dangerous)}"


def test_no_taios_qanxorus_memory_strings():
    for path in _cognitive_files():
        tree = _code_without_docstrings(path)
        code = ast.dump(tree)
        for token in ("TAIOS", "QanXorus", "sqlite", "embedding", "memory.db"):
            assert token not in code, f"{path.name}: {token}"


def test_p1_pins_intact():
    """Non-régression artefacts P1 (lecture seule, aucune écriture)."""
    for rel, digest in P1_PINS.items():
        data = (PROJECT_ROOT / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, rel


def test_p2_p3_imports_intact():
    """Compatibilité P2/P3 : modules existants toujours importables."""
    import jarvis  # noqa: F401
    import core.audio  # noqa: F401
    import core.wake.detector  # noqa: F401
    from tools import score_wavs  # noqa: F401

    assert jarvis.SAMPLE_RATE == 44100
