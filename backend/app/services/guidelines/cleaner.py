"""
HTML Cleaning, Text Normalization, and Language Detection.
Reference: Guideline Extraction Plan Section 7.2 Steps 1-5, 10.6 (GE-HTM), 10.7 (GE-LNG).
"""

from __future__ import annotations

import html
import re
import unicodedata
from bs4 import BeautifulSoup, Comment
import trafilatura
from langdetect import DetectorFactory, detect, LangDetectException

# Seed langdetect for deterministic results across runs (GE-LNG-05)
DetectorFactory.seed = 0


class CleanError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def count_words(text: str) -> int:
    """Counts words in text accurately by splitting on whitespace."""
    if not text:
        return 0
    return len(text.split())


def normalize_clean_text(raw_text: str) -> str:
    """
    Normalizes text:
    - Unicode NFC normalization
    - Replaces non-breaking spaces and zero-width characters
    - Normalizes repeated blank lines to at most two
    - Trims trailing spaces per line
    """
    if not raw_text:
        return ""

    # 1. Unicode NFC
    text = unicodedata.normalize("NFC", raw_text)

    # 2. Replace non-breaking spaces, zero-width chars, odd whitespace
    text = re.sub(r"[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]", " ", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # 3. Trim line ends and collapse spaces
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    
    # 4. Collapse repeated blank lines
    result_lines: list[str] = []
    consecutive_empty = 0
    for line in lines:
        if not line:
            consecutive_empty += 1
            if consecutive_empty <= 2:
                result_lines.append("")
        else:
            consecutive_empty = 0
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def extract_title_from_html(html_str: str) -> str | None:
    """Extracts the <title> tag text from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.IGNORECASE | re.DOTALL)
    if match:
        title = html.unescape(match.group(1))
        # Strip internal tags if any
        title = re.sub(r"<[^>]+>", "", title)
        title = normalize_clean_text(title)
        return title if title else None
    return None


def clean_html_with_bs4(html_str: str) -> str:
    """
    Fallback HTML parser using BeautifulSoup to clean and preserve structure:
    - Headings H1-H6 converted to Markdown headers (#, ##)
    - Lists converted to bullet lines
    - Tables converted to readable rows
    - Scripts, styles, nav, footer, headers stripped
    - Accordions (<details>) preserved
    """
    soup = BeautifulSoup(html_str, "html.parser")

    # Remove unwanted tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # Process Headings
    for i in range(1, 7):
        for h in soup.find_all(f"h{i}"):
            h_text = h.get_text(separator=" ", strip=True)
            if h_text:
                h.replace_with(f"\n\n{'#' * i} {h_text}\n\n")

    # Process Lists
    for li in soup.find_all("li"):
        li_text = li.get_text(separator=" ", strip=True)
        if li_text:
            li.replace_with(f"\n* {li_text}")

    # Process Tables: convert to markdown rows
    for table in soup.find_all("table"):
        rows_text = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows_text.append("| " + " | ".join(cells) + " |")
        if rows_text:
            table.replace_with("\n\n" + "\n".join(rows_text) + "\n\n")

    text = soup.get_text(separator="\n", strip=True)
    return text


def clean_guideline_content(
    content: str, is_html: bool = True
) -> tuple[str, str | None, list[dict[str, str]]]:
    """
    Cleans raw HTML or pasted text into normalized text/markdown.
    Returns: (cleaned_text, page_title, warnings)
    Raises CleanError if content is empty (< 30 words).
    """
    warnings: list[dict[str, str]] = []
    page_title: str | None = None

    if not content or not content.strip():
        raise CleanError("EMPTY_CONTENT", "No content provided.")

    if is_html:
        page_title = extract_title_from_html(content)
        
        # Check if content looks like a JS shell
        lower_raw = content.lower()
        if ("<div id=\"root\"></div>" in lower_raw or "<div id=\"app\"></div>" in lower_raw) and len(content) < 3000:
            warnings.append({
                "code": "CONTENT_MAY_BE_INCOMPLETE",
                "message": "Page appears to rely on client-side JavaScript rendering. Guideline text may be incomplete.",
            })

        # Try trafilatura first
        extracted = trafilatura.extract(
            content,
            include_links=False,
            include_images=False,
            include_tables=True,
            output_format="txt",
        )

        if not extracted or len(extracted.split()) < 30:
            # Fallback to BeautifulSoup
            extracted = clean_html_with_bs4(content)
    else:
        # User pasted markdown or plain text
        # If it contains html tags, clean them
        if "<p>" in content or "<div>" in content or "<br" in content:
            extracted = clean_html_with_bs4(content)
        else:
            extracted = content

    cleaned = normalize_clean_text(extracted)
    w_count = count_words(cleaned)

    # Word count thresholds
    if w_count < 30:
        raise CleanError("EMPTY_CONTENT", f"Only {w_count} words found. Minimum required is 30.")
    elif w_count < 150:
        warnings.append({
            "code": "INSUFFICIENT_GUIDELINE_CONTENT",
            "message": f"Only {w_count} words found in guideline text. Some extraction fields may be missing.",
        })

    return cleaned, page_title, warnings


def detect_guideline_language(text: str) -> tuple[str, list[dict[str, str]]]:
    """
    Detects language of cleaned text.
    Skips detection if under 50 words.
    Adds NOT_ENGLISH warning if detected language is not English.
    """
    warnings: list[dict[str, str]] = []
    w_count = count_words(text)
    if w_count < 50:
        return "en", warnings

    try:
        lang = detect(text[:2000])  # Sample first 2000 chars for speed & reliability
    except LangDetectException:
        return "unknown", warnings

    if lang != "en":
        warnings.append({
            "code": "NOT_ENGLISH",
            "message": f"Guidelines language detected as '{lang}'. Non-English guidelines may result in lower extraction accuracy.",
        })

    return lang, warnings
