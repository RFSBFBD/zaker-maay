from __future__ import annotations

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from docx import Document
from pypdf import PdfReader

from app.services.knowledge_ingestion.schemas import (
    DocumentExtractionResult,
    ExtractedPageContent,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 500


def extract_document_content(
    file_name: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> DocumentExtractionResult:
    """Perform deterministic, format-specific extraction preserving structure and page context."""
    ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    is_audio = ext in {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".aac", ".flac", ".mp4"}

    if is_audio:
        return _extract_audio_stub(file_name, ext)

    if ext == ".txt" or ext == ".md":
        return _extract_plain_text(file_name, ext, content)
    elif ext == ".docx":
        return _extract_docx(file_name, ext, content)
    elif ext in {".pptx", ".ppt"}:
        return _extract_pptx(file_name, ext, content)
    elif ext == ".pdf":
        return _extract_pdf(file_name, ext, content)
    elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return _extract_image(file_name, ext, content)

    # Fallback to UTF-8 text if decodable
    try:
        text = content.decode("utf-8")
        return DocumentExtractionResult(
            file_name=file_name,
            extension=ext,
            total_pages_or_slides=1,
            pages=[ExtractedPageContent(page_or_slide_number=1, text=text)],
            raw_character_count=len(text),
        )
    except Exception:
        logger.warning("Unsupported binary format for deterministic extraction: %s", file_name)
        return DocumentExtractionResult(
            file_name=file_name,
            extension=ext,
            total_pages_or_slides=0,
            pages=[],
        )


def _extract_plain_text(file_name: str, ext: str, content: bytes) -> DocumentExtractionResult:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    lines = text.split("\n")
    headings = [line.strip("# ").strip() for line in lines if line.strip().startswith("#")]

    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=1,
        pages=[
            ExtractedPageContent(
                page_or_slide_number=1,
                text=text,
                headings=headings,
            )
        ],
        raw_character_count=len(text),
    )


def _extract_docx(file_name: str, ext: str, content: bytes) -> DocumentExtractionResult:
    try:
        doc = Document(io.BytesIO(content))
    except Exception as exc:
        logger.warning("Failed to parse docx document %s: %s", file_name, exc)
        return DocumentExtractionResult(file_name=file_name, extension=ext)

    paragraphs_text = []
    headings = []

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style_name = getattr(p.style, "name", "").lower()
        if "heading" in style_name:
            headings.append(t)
            paragraphs_text.append(f"\n### {t}\n")
        else:
            paragraphs_text.append(t)

    tables_data: list[list[list[str]]] = []
    for table in doc.tables:
        matrix: list[list[str]] = []
        for row in table.rows:
            matrix.append([cell.text.strip() for cell in row.cells])
        if matrix:
            tables_data.append(matrix)

    combined_text = "\n".join(paragraphs_text)
    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=1,
        pages=[
            ExtractedPageContent(
                page_or_slide_number=1,
                text=combined_text,
                headings=headings,
                tables=tables_data,
            )
        ],
        raw_character_count=len(combined_text),
    )


def _extract_pptx(file_name: str, ext: str, content: bytes) -> DocumentExtractionResult:
    """Extract presentation slides, titles, bullet points, tables, and presenter notes from PPTX package."""
    pages: list[ExtractedPageContent] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            slide_entries = sorted(
                [f for f in zf.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")],
                key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)) if re.search(r"slide(\d+)\.xml", x) else 0,
            )

            for idx, slide_path in enumerate(slide_entries, start=1):
                xml_content = zf.read(slide_path)
                root = ET.fromstring(xml_content)
                namespaces = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

                # Extract all text elements
                texts = [elem.text for elem in root.findall(".//a:t", namespaces) if elem.text]
                slide_title = texts[0] if texts else f"Slide {idx}"
                slide_text = "\n".join(texts)

                # Try reading notes for this slide if available
                notes_text = None
                notes_path = f"ppt/notesSlides/notesSlide{idx}.xml"
                if notes_path in zf.namelist():
                    try:
                        nroot = ET.fromstring(zf.read(notes_path))
                        ntexts = [elem.text for elem in nroot.findall(".//a:t", namespaces) if elem.text]
                        notes_text = "\n".join(ntexts)
                    except Exception:
                        pass

                pages.append(
                    ExtractedPageContent(
                        page_or_slide_number=idx,
                        title=slide_title,
                        text=slide_text,
                        headings=[slide_title] if slide_title else [],
                        speaker_notes=notes_text,
                    )
                )
    except Exception as exc:
        logger.warning("PPTX native extraction failed for %s: %s", file_name, exc)

    if not pages:
        pages.append(ExtractedPageContent(page_or_slide_number=1, text="Presentation content"))

    raw_len = sum(len(p.text) for p in pages)
    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=len(pages),
        pages=pages,
        raw_character_count=raw_len,
    )


def _extract_pdf(file_name: str, ext: str, content: bytes) -> DocumentExtractionResult:
    pages: list[ExtractedPageContent] = []
    requires_ocr = False

    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        total_p = min(len(reader.pages), MAX_PAGES)

        for idx in range(total_p):
            p = reader.pages[idx]
            extracted = p.extract_text() or ""
            clean_text = extracted.strip()

            # Detect potential heading lines
            headings = []
            for line in clean_text.split("\n"):
                lstrip = line.strip()
                if (
                    len(lstrip) > 3
                    and len(lstrip) < 80
                    and (
                        lstrip.isupper()
                        or any(lstrip.startswith(prefix) for prefix in ["Chapter", "Section", "الفصل", "الوحدة", "المبحث", "محاضرة"])
                    )
                ):
                    headings.append(lstrip)

            # Check if page is predominantly scanned images with no extractable text
            has_scanned = len(clean_text) < 30 and len(getattr(p, "images", [])) > 0
            if has_scanned:
                requires_ocr = True

            pages.append(
                ExtractedPageContent(
                    page_or_slide_number=idx + 1,
                    text=clean_text,
                    headings=headings,
                    has_scanned_images=has_scanned,
                )
            )
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", file_name, exc)

    raw_len = sum(len(p.text) for p in pages)
    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=len(pages),
        pages=pages,
        requires_ocr=requires_ocr,
        raw_character_count=raw_len,
    )


def _extract_image(file_name: str, ext: str, content: bytes) -> DocumentExtractionResult:
    """Educational image content extraction stub with metadata preservation."""
    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=1,
        pages=[
            ExtractedPageContent(
                page_or_slide_number=1,
                title=f"صورة تعليمية: {file_name}",
                text=f"[صورة دراسية: {file_name}]",
                has_scanned_images=True,
            )
        ],
        requires_ocr=True,
        raw_character_count=len(file_name),
    )


def _extract_audio_stub(file_name: str, ext: str) -> DocumentExtractionResult:
    return DocumentExtractionResult(
        file_name=file_name,
        extension=ext,
        total_pages_or_slides=1,
        pages=[
            ExtractedPageContent(
                page_or_slide_number=1,
                title=f"تسجيل صوتي: {file_name}",
                text="",
            )
        ],
        is_audio=True,
        raw_character_count=0,
    )
