"""Wilfrid — formats P6.5 : EPUB/DOCX/HTML vers le modèle P6 (données seules).

Choix dépendances : stdlib (zipfile, xml.etree, html.parser) pour
EPUB/DOCX afin d'éviter lxml/ebooklib/python-docx sur Termux, avec
contrôle total (traversal, tailles, entités) ; beautifulsoup4
(html.parser, jamais lxml) pour le HTML réel. Contenu = donnée :
scripts/actifs neutralisés, URLs non suivies, macros ignorées, aucune
exécution. Sections ordonnées, métadonnées quand présentes, localisation
structurée (jamais de page inventée).
"""

from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

from core.knowledge.parsers import ParseError

MAX_ARCHIVE_FILES = 2000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_TEXT_CHARS = 10 * 1024 * 1024


def _safe_open_zip(path: Path) -> zipfile.ZipFile:
    """Ouvre une archive en refusant traversal, excès et corruption."""
    try:
        zf = zipfile.ZipFile(str(path), "r")
    except Exception as exc:
        raise ParseError(f"archive illisible: {type(exc).__name__}") from exc
    try:
        infos = zf.infolist()
    except Exception as exc:
        zf.close()
        raise ParseError(f"archive corrompue: {type(exc).__name__}") from exc
    if not infos:
        zf.close()
        raise ParseError("archive vide")
    if len(infos) > MAX_ARCHIVE_FILES:
        zf.close()
        raise ParseError("archive surdimensionnée (fichiers)")
    total = 0
    for info in infos:
        name = info.filename
        if not name or name.startswith("/") or ".." in name.split("/"):
            zf.close()
            raise ParseError("chemin dangereux dans l'archive")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            zf.close()
            raise ParseError("archive surdimensionnée (octets)")
    return zf


def _strip_text(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ------------------------------------------------------------------ EPUB
def parse_epub(path: str | Path) -> Dict[str, Any]:
    """EPUB → sections ordonnées (spine), métadonnées OPF."""
    zf = _safe_open_zip(Path(path))
    try:
        names = {info.filename for info in zf.infolist()}
        opf_name = next(
            (n for n in names if n.lower().endswith(".opf")), None)
        if opf_name is None:
            raise ParseError("EPUB sans manifeste OPF")
        try:
            opf = ET.fromstring(zf.read(opf_name))
        except Exception as exc:
            raise ParseError(f"OPF illisible: {type(exc).__name__}") from exc
        ns = {"opf": "http://www.idpf.org/2007/opf",
              "dc": "http://purl.org/dc/elements/1.1/"}

        def _find_text(parent, tag):
            node = parent.find(tag, ns)
            return (node.text or "").strip() if node is not None else ""

        metadata = opf.find("opf:metadata", ns)
        title = _find_text(metadata, "dc:title") if metadata is not None else ""
        author = _find_text(metadata, "dc:creator") if metadata is not None else ""
        manifest = {}
        if opf.find("opf:manifest", ns) is not None:
            for item in opf.find("opf:manifest", ns).findall("opf:item", ns):
                manifest[item.get("id", "")] = item.get("href", "")
        order = []
        spine = opf.find("opf:spine", ns)
        if spine is not None:
            for ref in spine.findall("opf:itemref", ns):
                href = manifest.get(ref.get("idref", ""), "")
                if href:
                    order.append(href)
        base = opf_name.rsplit("/", 1)[0]
        base = (base + "/") if base else ""
        sections: List[Dict[str, Any]] = []
        for href in order:
            name = base + href
            if name not in names:
                continue
            try:
                raw = zf.read(name)
            except Exception:
                continue
            text = _xhtml_to_text(raw)
            if text.strip():
                sections.append({"title": href, "text": text})
        if not sections:
            raise ParseError("EPUB sans contenu textuel")
        full = "\n\n".join(s["text"] for s in sections)
        if len(full) > MAX_TEXT_CHARS:
            raise ParseError("EPUB surdimensionné (texte)")
        return {
            "text": full,
            "pages": [{"n": i + 1, "text": s["text"]} for i, s in
                      enumerate(sections)],
            "meta": {"title": title, "author": author,
                     "sections": len(sections)},
            "status": "PARSED",
        }
    finally:
        zf.close()


# ------------------------------------------------------------------ DOCX
_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _docx_paragraph_text(paragraph) -> tuple[str, str]:
    """Retourne (style, texte) : titres détectés, reste en paragraphes."""
    style = ""
    ppr = paragraph.find("w:pPr", _DOCX_NS)
    if ppr is not None:
        pstyle = ppr.find("w:pStyle", _DOCX_NS)
        if pstyle is not None:
            style = str(pstyle.get(f"{{{_DOCX_NS['w']}}}val", ""))
    texts = []
    for node in paragraph.iter():
        if node.tag == f"{{{_DOCX_NS['w']}}}t":
            texts.append(node.text or "")
        elif node.tag in (f"{{{_DOCX_NS['w']}}}tab",
                          f"{{{_DOCX_NS['w']}}}br"):
            texts.append(" ")
    return style, "".join(texts)


def parse_docx(path: str | Path) -> Dict[str, Any]:
    """DOCX → paragraphes/titres (macros et objets ignorés, jamais exécutés)."""
    zf = _safe_open_zip(Path(path))
    try:
        try:
            raw = zf.read("word/document.xml")
        except KeyError as exc:
            raise ParseError("DOCX sans document.xml") from exc
        try:
            root = ET.fromstring(raw)
        except Exception as exc:
            raise ParseError(f"DOCX XML illisible: {type(exc).__name__}") from exc
        sections: List[Dict[str, Any]] = []
        current = {"title": "", "parts": []}
        for para in root.iter(f"{{{_DOCX_NS['w']}}}p"):
            style, text = _docx_paragraph_text(para)
            text = text.strip()
            if not text:
                continue
            if style.lower().startswith("heading"):
                if any(p.strip() for p in current["parts"]) or current["title"]:
                    sections.append({"title": current["title"],
                                     "text": "\n".join(current["parts"])})
                current = {"title": text, "parts": []}
            else:
                current["parts"].append(text)
        if any(p.strip() for p in current["parts"]) or current["title"]:
            sections.append({"title": current["title"],
                             "text": "\n".join(current["parts"])})
        if not sections:
            raise ParseError("DOCX sans contenu textuel")
        full = "\n\n".join(
            ((s["title"] + "\n") if s["title"] else "") + s["text"]
             for s in sections)
        if len(full) > MAX_TEXT_CHARS:
            raise ParseError("DOCX surdimensionné (texte)")
        core = None
        try:
            core = ET.fromstring(zf.read("docProps/core.xml"))
        except Exception:
            core = None
        title, author = "", ""
        if core is not None:
            dcterms = "http://purl.org/dc/terms/"
            for tag, key in (("title", "title"), ("creator", "author")):
                node = core.find(f"{{{dcterms}}}{tag}")
                if node is not None and node.text:
                    if key == "title":
                        title = node.text.strip()
                    else:
                        author = node.text.strip()
        return {
            "text": full,
            "pages": [{"n": i + 1, "text": s["text"]} for i, s in
                      enumerate(sections)],
            "meta": {"title": title, "author": author,
                     "sections": len(sections)},
            "status": "PARSED",
        }
    finally:
        zf.close()


# ------------------------------------------------------------------ HTML
class _TextExtractor(HTMLParser):
    """Extrait le texte, neutralise scripts/styles/événements/iframes."""

    _SKIP = frozenset({"script", "style", "noscript", "iframe", "object",
                       "embed", "template", "head"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._blocks: List[str] = []
        self._current: List[str] = []

    def _flush(self):
        text = "".join(self._current).strip()
        if text:
            self._blocks.append(text)
        self._current = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if tag in ("p", "div", "section", "article", "h1", "h2", "h3",
                   "h4", "h5", "h6", "li", "tr", "br", "hr", "title"):
            self._flush()
            if tag.startswith("h"):
                self._current.append("# ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in ("p", "div", "section", "article", "h1", "h2", "h3",
                   "h4", "h5", "h6", "li", "tr", "title"):
            self._flush()

    def handle_data(self, data):
        if self._skip_depth:
            return
        self._current.append(data)

    def result(self) -> List[str]:
        self._flush()
        return [b for b in self._blocks if b.strip()]


def parse_html(path: str | Path) -> Dict[str, Any]:
    """HTML → blocs texte (scripts/actifs neutralisés, liens non suivis)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ParseError("beautifulsoup4 indisponible") from exc
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ParseError(f"fichier inaccessible: {exc}") from exc
    if not raw.strip():
        raise ParseError("HTML vide")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("windows-1252")
        except UnicodeDecodeError as exc:
            raise ParseError("encodage indéterminé") from exc
    try:
        soup = BeautifulSoup(text, "html.parser")
    except Exception as exc:
        raise ParseError(f"HTML illisible: {type(exc).__name__}") from exc
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    for dead in soup(["script", "style", "noscript", "iframe", "object",
                      "embed", "template", "head"]):
        dead.decompose()
    extractor = _TextExtractor()
    try:
        extractor.feed(str(soup))
    except Exception as exc:
        raise ParseError(f"HTML malformé: {type(exc).__name__}") from exc
    blocks = extractor.result()
    if not blocks:
        raise ParseError("HTML sans contenu textuel")
    full = "\n\n".join(blocks)
    if len(full) > MAX_TEXT_CHARS:
        raise ParseError("HTML surdimensionné (texte)")
    return {
        "text": _strip_text(full),
        "pages": [{"n": i + 1, "text": b} for i, b in enumerate(blocks)],
        "meta": {"title": title, "blocks": len(blocks)},
        "status": "PARSED",
    }


def _xhtml_to_text(raw: bytes) -> str:
    """XHTML d'EPUB → texte (scripts neutralisés, sans exécution)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("windows-1252", errors="replace")
    extractor = _TextExtractor()
    try:
        extractor.feed(text)
    except Exception:
        return ""
    return _strip_text("\n\n".join(extractor.result()))


# ------------------------------------------------------- normalisation
def normalize_parsed(parsed: Dict[str, Any],
                     paged: bool = False) -> List[tuple]:
    """Converge vers le modèle P6 : [(ordinal, text, location)].

    `paged=True` uniquement pour les formats à pages réelles (PDF) :
    location = "page N". Sinon location structurée "section N" —
    jamais de page inventée, absence conservée comme "" côté appelant
    si non applicable.
    """
    out: List[tuple] = []
    for page in parsed.get("pages") or []:
        text = str(page.get("text", "") or "")
        if not text.strip():
            continue
        ordinal = int(page.get("n", len(out) + 1))
        if paged:
            location = f"page {ordinal}"
        else:
            location = f"section {ordinal}"
        out.append((ordinal, text, location))
    if not out and str(parsed.get("text", "") or "").strip():
        out = [(1, str(parsed["text"]), "")]
    return out
