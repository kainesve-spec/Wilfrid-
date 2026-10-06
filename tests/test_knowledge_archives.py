"""Tests P6.6 — archives hostiles : bombes, traversal, troncation (local)."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from core.knowledge import formats as F
from core.knowledge.parsers import ParseError


def _tmp():
    tmp = Path(tempfile.mkdtemp(prefix="p66z_"))
    return tmp


def _clean(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


def test_too_many_entries_refused():
    tmp = _tmp()
    try:
        path = tmp / "many.epub"
        with zipfile.ZipFile(str(path), "w") as zf:
            for i in range(2005):
                zf.writestr(f"f{i}.txt", b"x")
        with pytest.raises(ParseError):
            F._safe_open_zip(path)
    finally:
        _clean(tmp)


def test_declared_oversize_refused_before_read():
    # Bombe classique : 210 Mo de zéros compressés en ~200 Ko.
    # Le garde-fou doit refuser AVANT toute lecture du contenu.
    tmp = _tmp()
    try:
        path = tmp / "bomb.epub"
        with zipfile.ZipFile(str(path), "w",
                             compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.bin", b"\0" * (210 * 1024 * 1024))
        assert path.stat().st_size < 1024 * 1024  # petite sur disque
        with pytest.raises(ParseError):
            F._safe_open_zip(path)
    finally:
        _clean(tmp)


def test_traversal_and_absolute_refused():
    tmp = _tmp()
    try:
        for name in ("../../evil.txt", "/abs/evil.txt", "a/../../b.txt"):
            path = tmp / "trav.epub"
            with zipfile.ZipFile(str(path), "w") as zf:
                zf.writestr(name, b"x")
                zf.writestr("OEBPS/content.opf", b"<package/>")
            with pytest.raises(ParseError):
                F._safe_open_zip(path)
    finally:
        _clean(tmp)


def test_truncated_and_empty_archives():
    tmp = _tmp()
    try:
        full = tmp / "full.epub"
        with zipfile.ZipFile(str(full), "w") as zf:
            zf.writestr("OEBPS/content.opf", b"<package/>")
        data = full.read_bytes()
        cut = tmp / "cut.epub"
        cut.write_bytes(data[: max(10, len(data) // 2)])
        with pytest.raises(ParseError):
            F._safe_open_zip(cut)
        empty = tmp / "empty.epub"
        with zipfile.ZipFile(str(empty), "w"):
            pass
        with pytest.raises(ParseError):
            F._safe_open_zip(empty)
        garbage = tmp / "garbage.epub"
        garbage.write_bytes(b"\x00\x01 not a zip at all \xff\xfe")
        with pytest.raises(ParseError):
            F._safe_open_zip(garbage)
    finally:
        _clean(tmp)


def test_no_extraction_outside_tmp():
    tmp = _tmp()
    try:
        # P6 n'extrait jamais d'archive sur disque : lecture en flux seul.
        import core.knowledge.formats as fmt

        src = Path(fmt.__file__).read_text(encoding="utf-8")
        assert "extractall" not in src
        assert "extract(" not in src
    finally:
        _clean(tmp)
