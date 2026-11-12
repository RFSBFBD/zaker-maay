from __future__ import annotations

import logging
import re
from typing import Any

from app.services.knowledge_ingestion.schemas import (
    CanonicalMarkdownDocument,
    DocumentExtractionResult,
)

logger = logging.getLogger(__name__)


def convert_to_canonical_markdown(
    *,
    resource_id: str,
    subject_id: str,
    file_name: str,
    extracted: DocumentExtractionResult,
    subject_title: str = "",
) -> CanonicalMarkdownDocument:
    """Generate structured Canonical Markdown preserving meaning, equations, tables, and page citations."""
    title = _derive_document_title(file_name, extracted)
    chapter_num = _detect_chapter_number(file_name, extracted)

    md_lines: list[str] = []
    outline: list[str] = []
    equations: list[str] = []
    tables_count = 0
    source_refs: list[str] = []

    # 1. Document Title Header
    chapter_prefix = f"الفصل {chapter_num}: " if chapter_num is not None else ""
    main_heading = f"# {chapter_prefix}{title}"
    md_lines.append(main_heading)
    outline.append(main_heading)

    # Metadata block
    md_lines.append("")
    md_lines.append(f"> **المقرر / المادة**: {subject_title or 'مقرر دراسي'}")
    md_lines.append(f"> **المصدر الأصلي**: `{file_name}` | **عدد الصفحات/الشرائح**: {extracted.total_pages_or_slides}")
    md_lines.append("")

    # 2. Iterate pages / slides
    for page in extracted.pages:
        p_num = page.page_or_slide_number
        p_header = f"## صفحة / شريحة {p_num}" if p_num is not None else "## محتوى المرجع"
        if page.title and page.title != title:
            p_header += f": {page.title}"

        md_lines.append("---")
        md_lines.append(p_header)
        outline.append(p_header)

        # Headings inside page
        if page.headings:
            for h in page.headings:
                if h != page.title and h != title:
                    md_lines.append(f"### {h}")
                    outline.append(f"### {h}")

        # Page text content
        clean_text = page.text.strip()
        if clean_text:
            md_lines.append("")
            md_lines.append(clean_text)

        # Speaker notes if present (e.g. from PPTX)
        if page.speaker_notes and page.speaker_notes.strip():
            md_lines.append("")
            md_lines.append(f"**ملاحظات المحاضر (Speaker Notes)**:\n> {page.speaker_notes.strip()}")

        # Extracted Tables
        if page.tables:
            for matrix in page.tables:
                if not matrix or len(matrix) < 1:
                    continue
                tables_count += 1
                md_lines.append("")
                # Header row
                header_row = matrix[0]
                md_lines.append("| " + " | ".join(header_row) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header_row)) + " |")
                for row in matrix[1:]:
                    # Match header length
                    padded_row = list(row) + [""] * (len(header_row) - len(row))
                    md_lines.append("| " + " | ".join(padded_row[:len(header_row)]) + " |")
                md_lines.append("")

        # Source Reference line for traceability
        ref_line = f"مرجع المقطع: `{file_name}`, صفحة/شريحة {p_num or 1}"
        source_refs.append(f"- {ref_line}")
        md_lines.append("")
        md_lines.append(f"*{ref_line}*")
        md_lines.append("")

    # Detect equations in text (e.g. LaTeX formulas or mathematical lines)
    combined = "\n".join(md_lines)
    for eq_match in re.finditer(r"(\$\$[^\$]+\$\$|\\\[[^\]]+\\\]|[A-Za-z]\s*=\s*[0-9A-Za-z\+\-\*\/\^\(\)]+)", combined):
        eq_text = eq_match.group(1).strip()
        if len(eq_text) > 3 and eq_text not in equations:
            equations.append(eq_text)

    canonical_md_text = "\n".join(md_lines)

    return CanonicalMarkdownDocument(
        resource_id=resource_id,
        subject_id=subject_id,
        file_name=file_name,
        title=title,
        chapter_number=chapter_num,
        markdown_content=canonical_md_text,
        outline=outline,
        equations=equations[:10],
        tables_count=tables_count,
        source_references=source_refs,
    )


def _detect_chapter_number(file_name: str, extracted: DocumentExtractionResult) -> int | None:
    """Detect explicit chapter number from filename or internal page headings."""
    # 1. Filename match: "Chapter 4 - Routing", "Ch_2_Models", "الفصل 3"
    fn_matches = [
        re.search(r"(?:chapter|ch|chap|chpt|lec|lecture)[\s_-]*(\d+)", file_name, re.IGNORECASE),
        re.search(r"(?:الفصل|الباب|الوحدة|المحاضرة)[\s_-]*(\d+)", file_name, re.IGNORECASE),
        re.search(r"^(\d+)[\s_-]+", file_name),
    ]
    for m in fn_matches:
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

    # 2. Check first page headings
    if extracted.pages:
        first_page = extracted.pages[0]
        for h in first_page.headings:
            hm = re.search(r"(?:chapter|ch|الفصل|الوحدة)[\s_-]*(\d+)", h, re.IGNORECASE)
            if hm:
                try:
                    return int(hm.group(1))
                except ValueError:
                    pass

    return None


def _derive_document_title(file_name: str, extracted: DocumentExtractionResult) -> str:
    """Derive clean human-readable title from internal headings or filename stem."""
    # If first page has an explicit strong title/heading, prefer internal title
    if extracted.pages:
        first_page = extracted.pages[0]
        if first_page.title and not first_page.title.lower().startswith("slide"):
            return first_page.title.strip()
        if first_page.headings:
            for h in first_page.headings:
                if len(h) > 4 and not h.lower().startswith("chapter"):
                    return h.strip()

    # Fallback to sanitized filename stem
    stem = file_name.rsplit(".", 1)[0]
    stem = re.sub(r"^[0-9]+[\s_-]*", "", stem)
    stem = re.sub(r"[\-_]+", " ", stem).strip()
    return stem or file_name
