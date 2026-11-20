"""
Relevance Filtering and Deterministic Text Chunking for Guideline Extraction.
Reference: Guideline Extraction Plan Section 7.2 Steps 6-7, 10.8 (GE-CHK).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MAX_WHOLE_TEXT_CHARS = 24000
MAX_CHUNK_CHARS = 6000
CHUNK_OVERLAP_CHARS = 200
MAX_CHUNKS_LIMIT = 12

RELEVANCE_KEYWORDS = [
    "manuscript preparation", "submission guidelines", "author guidelines",
    "word limit", "word count", "page limit", "abstract", "keywords",
    "references", "citations", "citation style", "bibliography",
    "figures", "tables", "illustrations", "dpi", "image resolution",
    "article types", "original article", "research article", "review article",
    "structure", "sections", "methods", "results", "discussion",
    "file formats", "docx", "latex", "pdf",
    "ethics", "declarations", "conflict of interest", "data availability",
    "blinded review", "double-blind", "single-blind", "peer review",
    "template", "margins", "font", "spacing", "cover letter"
]


@dataclass
class TextChunk:
    chunk_index: int
    total_chunks: int
    heading_path: str
    text: str
    relevance_score: float = 0.0


def score_text_relevance(text: str, heading: str = "") -> float:
    """Calculates relevance score based on keyword frequency in heading and body."""
    combined = f"{heading} {heading} {text}".lower()
    score = 0.0
    for kw in RELEVANCE_KEYWORDS:
        if kw in combined:
            score += 1.0 + combined.count(kw) * 0.5
    return score


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Splits text by markdown headings (#, ##, ###).
    Returns list of (heading_path, section_content).
    If no headings, returns [("", text)].
    """
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    
    current_headings: list[str] = []
    current_lines: list[str] = []
    heading_level = 0

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            # Save previous section if exists
            content = "\n".join(current_lines).strip()
            if content:
                h_path = " > ".join(current_headings)
                sections.append((h_path, content))
                current_lines = []

            level = len(m.group(1))
            title = m.group(2).strip()

            # Adjust heading stack
            if level <= heading_level and current_headings:
                current_headings = current_headings[:level - 1]
            current_headings.append(title)
            heading_level = level
        else:
            current_lines.append(line)

    content = "\n".join(current_lines).strip()
    if content:
        h_path = " > ".join(current_headings)
        sections.append((h_path, content))

    if not sections and text.strip():
        sections.append(("", text.strip()))

    return sections


def split_large_paragraph(para: str, max_chars: int) -> list[str]:
    """Splits a single oversized paragraph at sentence boundaries."""
    if len(para) <= max_chars:
        return [para]

    # Split by sentences (. ! ?)
    sentences = re.split(r"(?<=[.!?])\s+", para)
    parts: list[str] = []
    current_part: list[str] = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) + 1 > max_chars and current_part:
            parts.append(" ".join(current_part))
            current_part = [sent]
            current_len = len(sent)
        else:
            current_part.append(sent)
            current_len += len(sent) + 1

    if current_part:
        parts.append(" ".join(current_part))

    return parts


def chunk_section_content(
    heading_path: str, content: str, max_chunk_size: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[str]:
    """Chunks section content by paragraph boundaries with small overlap."""
    if len(content) <= max_chunk_size:
        return [content]

    raw_paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        if len(p) > max_chunk_size:
            paragraphs.extend(split_large_paragraph(p, max_chunk_size))
        else:
            paragraphs.append(p)

    chunks: list[str] = []
    current_paras: list[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)
        if current_len + p_len + 2 > max_chunk_size and current_paras:
            chunks.append("\n\n".join(current_paras))
            # Start next chunk with overlap paragraph if possible
            last_p = current_paras[-1]
            if len(last_p) <= overlap:
                current_paras = [last_p, p]
                current_len = len(last_p) + p_len + 2
            else:
                current_paras = [p]
                current_len = p_len
        else:
            current_paras.append(p)
            current_len += p_len + 2

    if current_paras:
        chunks.append("\n\n".join(current_paras))

    return chunks


def build_text_chunks(cleaned_text: str) -> tuple[list[TextChunk], list[dict[str, str]]]:
    """
    Builds deterministic chunks from cleaned text.
    - If total text <= 24,000 characters: returns 1 single chunk.
    - If > 24,000 characters: breaks into scored sections by headings,
      filters and prioritizes by relevance, limits to 12 chunks, adds TRUNCATED warning if cut.
    """
    warnings: list[dict[str, str]] = []

    if len(cleaned_text) <= MAX_WHOLE_TEXT_CHARS:
        return [
            TextChunk(
                chunk_index=0,
                total_chunks=1,
                heading_path="",
                text=cleaned_text,
                relevance_score=score_text_relevance(cleaned_text),
            )
        ], warnings

    sections = split_into_sections(cleaned_text)
    
    # Score each section and chunk
    scored_items: list[tuple[float, str, str]] = []
    for h_path, s_text in sections:
        if not s_text.strip():
            continue
        score = score_text_relevance(s_text, h_path)
        sub_chunks = chunk_section_content(h_path, s_text)
        for sub in sub_chunks:
            scored_items.append((score, h_path, sub))

    # If items exceed limit, prioritize highest score
    truncated = False
    if len(scored_items) > MAX_CHUNKS_LIMIT:
        truncated = True
        warnings.append({
            "code": "TRUNCATED",
            "message": f"Guideline text exceeded {MAX_CHUNKS_LIMIT} chunks; lowest relevance sections were omitted.",
        })
        # Sort by score descending, take top 12
        scored_items.sort(key=lambda x: x[0], reverse=True)
        scored_items = scored_items[:MAX_CHUNKS_LIMIT]
        # Restore natural order or stable order

    chunks: list[TextChunk] = []
    total = len(scored_items)
    for idx, (score, h_path, sub_text) in enumerate(scored_items):
        chunks.append(
            TextChunk(
                chunk_index=idx,
                total_chunks=total,
                heading_path=h_path,
                text=sub_text,
                relevance_score=score,
            )
        )

    return chunks, warnings

