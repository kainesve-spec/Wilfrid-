"""Tests P6.2 — parsers TXT/PDF (fixtures déterministes, sans réseau)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.knowledge import parsers as P


def _tmpfile(suffix: str, data: bytes) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="p62p_"))
    path = tmp / ("doc" + suffix)
    path.write_bytes(data)
    return path


def _pdf_bytes(pages_text):
    """PDF valides assemblés avec pypdf (1 page artisanale × N fusionnées)."""
    from pypdf import PdfReader, PdfWriter

    if len(pages_text) == 1:
        return _single_page_pdf(pages_text[0])
    writer = PdfWriter()
    for text in pages_text:
        reader = PdfReader(__import__("io").BytesIO(_single_page_pdf(text)))
        writer.add_page(reader.pages[0])
    import io as _io

    buf = _io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _single_page_pdf(text):
    """PDF minimal artisanal à une page avec opérateurs BT/Tj."""
    content = (f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET").encode("latin-1")
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 "
         "5 0 R >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>"),
        (f"<< /Length {len(content)} >>\nstream\n".encode("latin-1")
         + content + b"\nendstream"),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        data = obj if isinstance(obj, bytes) else obj.encode("latin-1")
        out += f"{num} 0 obj\n".encode("latin-1") + data + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode("latin-1")
    return bytes(out)


def test_txt_utf8_and_metadata():
    path = _tmpfile(".txt", "Bonjour Wilfrid.\nDeuxième ligne.\n".encode("utf-8"))
    try:
        res = P.parse_txt(path)
        assert res["status"] == "PARSED"
        assert "Bonjour Wilfrid." in res["text"]
        assert res["meta"]["encoding"] == "utf-8"
        assert len(res["pages"]) == 1
    finally:
        import shutil

        shutil.rmtree(path.parent, ignore_errors=True)


def test_txt_empty_and_invalid():
    empty = _tmpfile(".txt", b"")
    try:
        with pytest.raises(P.ParseError):
            P.parse_txt(empty)
    finally:
        import shutil

        shutil.rmtree(empty.parent, ignore_errors=True)
    with pytest.raises(P.ParseError):
        P.parse_document("/tmp/nonexistent-xyz.txt")


def test_txt_latin1_fallback_noted():
    path = _tmpfile(".txt", "crème brûlée\n".encode("latin-1"))
    try:
        res = P.parse_txt(path)
        assert res["meta"]["encoding"] == "windows-1252-fallback"
        assert "crème" in res["text"]
    finally:
        import shutil

        shutil.rmtree(path.parent, ignore_errors=True)


def test_pdf_valid_multipage_and_metadata():
    data = _pdf_bytes(["Wilfrid page une", "Wilfrid page deux"])
    path = _tmpfile(".pdf", data)
    try:
        res = P.parse_pdf(path)
        assert res["status"] == "PARSED"
        assert len(res["pages"]) == 2
        assert "page une" in res["pages"][0]["text"]
        assert "page deux" in res["pages"][1]["text"]
        assert res["meta"]["pages"] == 2
    finally:
        import shutil

        shutil.rmtree(path.parent, ignore_errors=True)


def test_pdf_encrypted_refused():
    from pypdf import PdfReader, PdfWriter

    tmp = Path(tempfile.mkdtemp(prefix="p62enc_"))
    try:
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.encrypt("secret")
        path = tmp / "enc.pdf"
        with open(path, "wb") as fh:
            writer.write(fh)
        assert PdfReader(str(path)).is_encrypted
        with pytest.raises(P.ParseError):
            P.parse_pdf(path)
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_pdf_corrupt_and_empty_and_no_text():
    bad = _tmpfile(".pdf", b"%PDF-1.4\ntrailer-broken{{{")
    try:
        with pytest.raises(P.ParseError):
            P.parse_pdf(bad)
    finally:
        import shutil

        shutil.rmtree(bad.parent, ignore_errors=True)
    from pypdf import PdfWriter

    tmp = Path(tempfile.mkdtemp(prefix="p62blank_"))
    try:
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        path = tmp / "blank.pdf"
        with open(path, "wb") as fh:
            writer.write(fh)
        res = P.parse_pdf(path)
        assert res["status"] == "NO_TEXT_LAYER"
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_dispatcher_refuses_other_formats():
    path = _tmpfile(".epub", b"PK fake")
    try:
        with pytest.raises(P.ParseError):
            P.parse_document(path)
    finally:
        import shutil

        shutil.rmtree(path.parent, ignore_errors=True)
