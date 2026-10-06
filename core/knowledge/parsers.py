"""Wilfrid — parsers P6.2 : TXT + PDF uniquement (données, jamais d'exécution).

TXT (.txt, text/plain) : UTF-8, détection raisonnable, erreurs signalées.
PDF (pypdf) : texte + pages + métadonnées ; chiffré/corrompu/vide refusés ;
sans couche texte → statut NO_TEXT_LAYER explicite (pas d'OCR en P6.2).
EPUB/DOCX/HTML : refusés (P6.3+).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class ParseError(ValueError):
    """Document illisible ou vide : refus explicite, jamais de vide silencieux."""


def parse_txt(path: str | Path) -> Dict[str, Any]:
    """Lit un texte : détection UTF-8 puis repli latin-1 documenté."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ParseError(f"fichier inaccessible: {exc}") from exc
    if not data:
        raise ParseError("texte vide")
    encoding = "utf-8"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("windows-1252")
            encoding = "windows-1252-fallback"
        except UnicodeDecodeError as exc:
            raise ParseError(f"encodage indéterminé: {exc}") from exc
    if not text.strip():
        raise ParseError("texte vide après décodage")
    lines = text.splitlines()
    return {
        "text": text,
        "pages": [{"n": 1, "text": text}],
        "meta": {"encoding": encoding, "lines": len(lines),
                 "chars": len(text)},
        "status": "PARSED",
    }


def parse_pdf(path: str | Path) -> Dict[str, Any]:
    """Extrait texte + pages + métadonnées via pypdf (lecture seule)."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ParseError("pypdf indisponible") from exc
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ParseError(f"PDF illisible: {type(exc).__name__}") from exc
    if getattr(reader, "is_encrypted", False):
        raise ParseError("PDF chiffré/protégé : refusé")
    pages: List[Dict[str, Any]] = []
    try:
        for i, page in enumerate(reader.pages):
            try:
                content = page.extract_text() or ""
            except Exception:
                content = ""
            pages.append({"n": i + 1, "text": content})
    except Exception as exc:
        raise ParseError(f"PDF corrompu: {type(exc).__name__}") from exc
    if not pages:
        raise ParseError("PDF sans pages")
    full = "\n".join(p.get("text", "") for p in pages)
    if not full.strip():
        info = getattr(reader, "metadata", None)
        return {
            "text": "",
            "pages": pages,
            "meta": {"title": str(getattr(info, "title", "") or ""),
                     "author": str(getattr(info, "author", "") or ""),
                     "pages": len(pages)},
            "status": "NO_TEXT_LAYER",
        }
    info = getattr(reader, "metadata", None)
    return {
        "text": full,
        "pages": pages,
        "meta": {"title": str(getattr(info, "title", "") or ""),
                 "author": str(getattr(info, "author", "") or ""),
                 "pages": len(pages), "chars": len(full)},
        "status": "PARSED",
    }


def parse_document(path: str | Path, mime_hint: str = "") -> Dict[str, Any]:
    """Routeur : txt/plain, pdf, epub, docx, html (P6.2 + P6.5)."""
    suffix = Path(path).suffix.lower()
    hint = (mime_hint or "").lower()
    if suffix == ".txt" or "text/plain" in hint:
        return parse_txt(path)
    if suffix == ".pdf" or "application/pdf" in hint:
        return parse_pdf(path)
    if suffix == ".epub" or "epub" in hint:
        from core.knowledge.formats import parse_epub

        return parse_epub(path)
    if suffix in (".docx",) or "officedocument" in hint:
        from core.knowledge.formats import parse_docx

        return parse_docx(path)
    if suffix in (".html", ".htm") or "text/html" in hint:
        from core.knowledge.formats import parse_html

        return parse_html(path)
    raise ParseError(f"format non supporté: {suffix or hint or '?'}")
