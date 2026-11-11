"""
Guideline Extraction Grounding and Confidence Computation Module.

Computes confidence scores ('high', 'medium', 'low') deterministically
by validating extracted evidence and rule values against source text.
Reference: Guideline Extraction Plan Sections 4.4, 7.4 Step 2, and 10.3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal
from rapidfuzz import fuzz

# Number words mapping from 0 to 100
_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen"
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"
]

NUMBER_WORDS: dict[int, list[str]] = {}
for i in range(20):
    NUMBER_WORDS[i] = [_ONES[i]]
NUMBER_WORDS[0].extend(["none", "no"])

for t_idx in range(2, 10):
    tens_val = t_idx * 10
    NUMBER_WORDS[tens_val] = [_TENS[t_idx]]
    for o_idx in range(1, 10):
        val = tens_val + o_idx
        NUMBER_WORDS[val] = [
            f"{_TENS[t_idx]}-{_ONES[o_idx]}",
            f"{_TENS[t_idx]} {_ONES[o_idx]}",
        ]

NUMBER_WORDS[100] = ["one hundred", "a hundred", "hundred"]


def normalize_text_for_matching(text: str | None) -> str:
    """
    Normalizes text for robust substring matching:
    - Normalizes smart quotes and apostrophes to standard " and '
    - Normalizes en-dashes, em-dashes, minus signs, and hyphens to -
    - Replaces all whitespace variants (non-breaking spaces, zero-width spaces, newlines) with ' '
    - Collapses multiple whitespace
    - Case-folds to lowercase
    """
    if not text:
        return ""
    
    # Quotes
    s = re.sub(r'[\u201c\u201d\u00ab\u00bb\u201e\u201f]', '"', text)
    s = re.sub(r'[\u2018\u2019\u201a\u201b\u02bb\u02bc`]', "'", s)
    
    # Dashes
    s = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', '-', s)
    
    # Non-breaking spaces and other Unicode spaces
    s = re.sub(r'[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]', ' ', s)
    
    # Replace control chars, newlines, carriage returns with space
    s = re.sub(r'[\r\n\t]+', ' ', s)
    
    # Collapse multiple spaces and lowercase
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def build_number_patterns(value: int | float) -> list[str]:
    """
    Builds regex pattern strings matching the number in digits (with separators)
    or words (for integers 0-100), bounded by non-digits or word boundaries.
    """
    patterns: list[str] = []
    
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        int_val = int(value)
        # 1. Plain digits
        s_val = str(int_val)
        
        # 2. Formatted with comma / space / period separators
        # e.g. 8000 -> 8,000 | 8 000 | 8.000
        formatted_variants = [s_val]
        if len(s_val) > 3:
            with_comma = f"{int_val:,}"
            formatted_variants.append(with_comma)
            formatted_variants.append(with_comma.replace(",", " "))
            formatted_variants.append(with_comma.replace(",", r"\."))
        
        digits_re = "|".join(re.escape(v) if r"\." not in v else v for v in set(formatted_variants))
        patterns.append(rf"(?<!\d)(?:{digits_re})(?!\d)")
        
        # 3. English number words up to 100
        if int_val in NUMBER_WORDS:
            words = NUMBER_WORDS[int_val]
            words_re = "|".join(re.escape(w) for w in words)
            patterns.append(rf"\b(?:{words_re})\b")
    else:
        # Float value
        f_val = float(value)
        f_str = f"{f_val:g}"
        f_comma = f_str.replace(".", ",")
        patterns.append(rf"(?<!\d)(?:{re.escape(f_str)}|{re.escape(f_comma)})(?!\d)")
        
    return patterns


def check_number_in_text(value: int | float, normalized_text: str) -> bool:
    """
    Checks whether a number appears in the normalized text as digits,
    with thousand separators, or as an English word (1-100).
    Ensures digits are not part of a larger number (e.g. 18000 for 8000).
    """
    if not normalized_text:
        return False
    patterns = build_number_patterns(value)
    for pat in patterns:
        if re.search(pat, normalized_text, re.IGNORECASE):
            return True
    return False


def check_word_in_text(word: str, normalized_text: str) -> bool:
    """
    Checks whether a keyword, enum value, or section appears in normalized text.
    Handles hyphens vs spaces and word boundaries.
    """
    if not word or not normalized_text:
        return False
    norm_w = normalize_text_for_matching(word)
    if not norm_w:
        return False
    # Check exact substring first
    if norm_w in normalized_text:
        return True
    # Word boundary regex with hyphen/space tolerance
    alt = re.sub(r'[\s\-_]+', r'[\\s\\-_]+', re.escape(norm_w))
    if re.search(rf"\b{alt}\b", normalized_text, re.IGNORECASE):
        return True
    return False


@dataclass
class GroundingResult:
    confidence: Literal["high", "medium", "low"]
    evidence: str
    grounded: bool
    evidence_status: Literal["exact", "fuzzy", "not_found", "empty"]
    warnings: list[dict[str, str]] = field(default_factory=list)


def compute_grounding(
    value: Any,
    evidence: str | None,
    source_text: str | None,
    field_path: str = "",
    fuzzy_threshold: float = 90.0,
) -> GroundingResult:
    """
    Computes confidence score and grounding metadata according to Section 4.4:
    - high: Evidence found in source (exact after normalization) and, for numbers,
            the number appears in the evidence.
    - medium: Evidence matched fuzzy (>= threshold), or number appears in source but not evidence.
    - low: Evidence not found, empty, or number does not appear anywhere in source ("ungrounded").
    
    Evidence longer than 300 characters is truncated to 300 for storage (GE-GRD-12).
    """
    warnings: list[dict[str, str]] = []
    
    # 1. Truncate evidence for storage
    stored_evidence = (evidence or "")[:300]
    
    # 2. Check empty evidence
    if not evidence or not evidence.strip():
        warnings.append({
            "code": "MISSING_EVIDENCE",
            "message": f"Evidence is missing or whitespace for field '{field_path}'.",
            "path": field_path,
        })
        return GroundingResult(
            confidence="low",
            evidence="",
            grounded=False,
            evidence_status="empty",
            warnings=warnings,
        )
        
    if not source_text or not source_text.strip():
        warnings.append({
            "code": "MISSING_SOURCE",
            "message": f"Source text is empty.",
            "path": field_path,
        })
        return GroundingResult(
            confidence="low",
            evidence=stored_evidence,
            grounded=False,
            evidence_status="not_found",
            warnings=warnings,
        )
        
    norm_source = normalize_text_for_matching(source_text)
    norm_evidence = normalize_text_for_matching(evidence)
    
    # 3. Evidence matching in source
    evidence_status: Literal["exact", "fuzzy", "not_found"]
    if norm_evidence in norm_source:
        evidence_status = "exact"
    else:
        # RapidFuzz fallback
        ratio = fuzz.partial_ratio(norm_evidence, norm_source)
        if ratio >= fuzzy_threshold:
            evidence_status = "fuzzy"
        else:
            evidence_status = "not_found"
            
    if evidence_status == "not_found":
        warnings.append({
            "code": "UNGROUNDED_EVIDENCE",
            "message": f"Evidence quote was not found in the source text for '{field_path}'.",
            "path": field_path,
        })
        return GroundingResult(
            confidence="low",
            evidence=stored_evidence,
            grounded=False,
            evidence_status="not_found",
            warnings=warnings,
        )

    # 4. Value grounding checks
    if value is None:
        # Null value with found evidence
        return GroundingResult(
            confidence="high" if evidence_status == "exact" else "medium",
            evidence=stored_evidence,
            grounded=True,
            evidence_status=evidence_status,
            warnings=warnings,
        )

    # 4a. Numeric value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        in_source = check_number_in_text(value, norm_source)
        in_evidence = check_number_in_text(value, norm_evidence)
        
        if not in_source:
            warnings.append({
                "code": "UNGROUNDED_VALUES",
                "message": f"Number {value} at '{field_path}' does not appear anywhere in source text.",
                "path": field_path,
            })
            return GroundingResult(
                confidence="low",
                evidence=stored_evidence,
                grounded=False,
                evidence_status=evidence_status,
                warnings=warnings,
            )
            
        if evidence_status == "exact" and in_evidence:
            return GroundingResult(
                confidence="high",
                evidence=stored_evidence,
                grounded=True,
                evidence_status="exact",
                warnings=warnings,
            )
        else:
            # Number in source but not in evidence, or evidence was fuzzy
            return GroundingResult(
                confidence="medium",
                evidence=stored_evidence,
                grounded=True,
                evidence_status=evidence_status,
                warnings=warnings,
            )

    # 4b. String or Enum value
    if isinstance(value, str):
        # Check if the word or phrase appears in source
        in_source = check_word_in_text(value, norm_source)
        in_evidence = check_word_in_text(value, norm_evidence)
        
        if not in_source:
            # Not in source at all -> low
            warnings.append({
                "code": "UNGROUNDED_VALUES",
                "message": f"Value '{value}' at '{field_path}' was not mentioned in source text.",
                "path": field_path,
            })
            return GroundingResult(
                confidence="low",
                evidence=stored_evidence,
                grounded=False,
                evidence_status=evidence_status,
                warnings=warnings,
            )
            
        if evidence_status == "exact" and in_evidence:
            return GroundingResult(
                confidence="high",
                evidence=stored_evidence,
                grounded=True,
                evidence_status="exact",
                warnings=warnings,
            )
        else:
            return GroundingResult(
                confidence="medium",
                evidence=stored_evidence,
                grounded=True,
                evidence_status=evidence_status,
                warnings=warnings,
            )

    # 4c. Boolean or complex structure
    # For booleans or structures, rely on evidence match quality
    conf: Literal["high", "medium"] = "high" if evidence_status == "exact" else "medium"
    return GroundingResult(
        confidence=conf,
        evidence=stored_evidence,
        grounded=True,
        evidence_status=evidence_status,
        warnings=warnings,
    )

