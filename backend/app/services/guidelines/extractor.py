"""
Guideline Extraction Orchestrator, Findings Merger, and Draft Assembler.
Reference: Guideline Extraction Plan Section 7.3, 7.4, 10.9 (GE-LLM), 10.10 (GE-MRG), 10.11 (GE-INJ).
"""

from __future__ import annotations

import asyncio
import copy
import re
from typing import Any, Literal

from app.services.guidelines.chunker import TextChunk
from app.services.guidelines.grounding import compute_grounding
from app.services.guidelines.llm.base import (
    BaseLLMClient,
    Finding,
    LLMExtractResult,
    LLMError,
    WHITELISTED_PATHS,
)
from app.services.guidelines.schema import (
    GuidelineRuleSchema,
    canonicalize_section_name,
    clean_string,
    normalize_integer_value,
    normalize_float_value,
)

CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}

# Scoped paths inside articleTypes
ARTICLE_TYPE_SCOPED_PATHS = {
    "maxWords", "maxAbstractWords", "requiredSections",
    "maxFigures", "maxTables", "maxReferences", "notes",
}

LIST_PATHS = {
    "general.requiredSections",
    "general.requiredStatements",
    "general.wordLimitExcludes",
    "figures.formats",
    "submission.fileFormats",
    "requiredSections",  # scoped
}

NUMERIC_RANGES = {
    "general.maxWords": (100, 100000),
    "general.minWords": (0, 100000),
    "general.maxAbstractWords": (20, 1000),
    "general.keywords.min": (0, 30),
    "general.keywords.max": (1, 30),
    "general.maxTitleChars": (10, 500),
    "citation.maxReferences": (1, 1000),
    "layout.fontSizePt": (6.0, 24.0),
    "layout.lineSpacing": (1.0, 3.0),
    "layout.maxPages": (1, 200),
    "figures.maxFigures": (0, 200),
    "figures.maxTables": (0, 200),
    "figures.minDpi": (72, 1200),
    # scoped article type ranges
    "maxWords": (100, 100000),
    "maxAbstractWords": (20, 1000),
    "maxFigures": (0, 200),
    "maxTables": (0, 200),
    "maxReferences": (1, 1000),
}


def validate_and_normalize_finding_value(path: str, raw_value: Any) -> Any:
    """
    Validates and normalizes individual finding value against schema constraints.
    Returns normalized value, or raises ValueError if invalid type or out of range.
    """
    if raw_value is None:
        return None

    # HTML tag and script stripping for string values (GE-INJ-06)
    if isinstance(raw_value, str):
        raw_value = clean_string(raw_value)
        if raw_value and len(raw_value) > 500:
            raw_value = raw_value[:500]

    # Numeric fields check
    if path in NUMERIC_RANGES:
        min_v, max_v = NUMERIC_RANGES[path]
        if isinstance(min_v, float):
            num = normalize_float_value(raw_value)
        else:
            num = normalize_integer_value(raw_value)
            
        if num < min_v or num > max_v:
            raise ValueError(f"Value {num} for {path} is out of permitted range [{min_v}, {max_v}]")
        return num

    # Boolean fields
    if path in ("citation.numbered", "submission.coverLetterRequired", "submission.highlightsRequired"):
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            low = raw_value.lower().strip()
            if low in ("true", "yes", "required"):
                return True
            if low in ("false", "no", "optional"):
                return False
        raise ValueError(f"Invalid boolean value '{raw_value}' for {path}")

    # Canonical section lists
    if path in ("general.requiredSections", "requiredSections"):
        if isinstance(raw_value, list):
            return [canonicalize_section_name(str(s)) for s in raw_value if clean_string(str(s))]
        elif isinstance(raw_value, str):
            return [canonicalize_section_name(raw_value)]
        raise ValueError("requiredSections must be a list or string")

    # List fields
    if path in LIST_PATHS:
        if isinstance(raw_value, list):
            return [clean_string(str(s)) for s in raw_value if clean_string(str(s))]
        elif isinstance(raw_value, str):
            return [clean_string(raw_value)]
        raise ValueError(f"{path} must be a list")

    return raw_value


async def extract_chunk_findings_with_retry(
    chunk: TextChunk, client: BaseLLMClient, max_repairs: int = 1
) -> list[Finding]:
    """
    Extracts findings from one chunk with repair attempt if JSON is malformed.
    """
    repair_count = 0
    last_error_msg = ""

    while True:
        try:
            res = await client.extract_findings(
                chunk.text,
                heading_path=chunk.heading_path,
                repair_context=last_error_msg if repair_count > 0 else None,
            )
            return res.findings
        except LLMError as e:
            if e.code == "LLM_INVALID_OUTPUT" and repair_count < max_repairs:
                repair_count += 1
                last_error_msg = e.message
                continue
            raise


async def orchestrate_extraction(
    chunks: list[TextChunk],
    client: BaseLLMClient,
    source_text: str | None = None,
    concurrency_limit: int = 3,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, int]]:
    """
    Runs extraction across all text chunks with bounded concurrency (default 3),
    merges findings, runs grounding checks, resolves conflicts, and produces draft.
    """
    warnings: list[dict[str, str]] = []
    token_usage = {"input_tokens": 0, "output_tokens": 0}

    sem = asyncio.Semaphore(concurrency_limit)
    all_findings: list[Finding] = []
    chunk_errors = 0

    async def _process_chunk(chunk: TextChunk):
        nonlocal chunk_errors
        async with sem:
            try:
                findings = await extract_chunk_findings_with_retry(chunk, client)
                all_findings.extend(findings)
            except LLMError as e:
                chunk_errors += 1
                if len(chunks) == 1 or chunk_errors == len(chunks):
                    raise
                warnings.append({
                    "code": "PARTIAL_CHUNK_FAILURE",
                    "message": f"Chunk {chunk.chunk_index} failed to extract: {e.message}",
                })

    # Run chunks concurrently
    tasks = [_process_chunk(c) for c in chunks]
    await asyncio.gather(*tasks)

    # 1. Filter findings (whitelisted paths, validation, range check)
    valid_findings: list[Finding] = []
    for f in all_findings:
        # Check path whitelist (GE-LLM-04)
        if f.path not in WHITELISTED_PATHS:
            warnings.append({
                "code": "UNKNOWN_PATH_DROPPED",
                "message": f"Dropped finding with unrecognized path: '{f.path}'",
                "path": f.path,
            })
            continue

        # Cap evidence at 300 characters (GE-INJ-07)
        evidence = (f.evidence or "")[:300]
        f.evidence = evidence

        # Validate and normalize value type & range (GE-LLM-05, GE-LLM-06)
        try:
            norm_val = validate_and_normalize_finding_value(f.path, f.value)
            f.value = norm_val
        except ValueError as e:
            warnings.append({
                "code": "INVALID_FINDING_VALUE",
                "message": f"Dropped invalid finding at '{f.path}': {e}",
                "path": f.path,
            })
            continue

        # Grounding check (GE-GRD)
        grounding = compute_grounding(f.value, f.evidence, source_text, f.path)
        f.confidence = grounding.confidence
        f.evidence = grounding.evidence
        if grounding.warnings:
            warnings.extend(grounding.warnings)

        valid_findings.append(f)

    if not valid_findings:
        warnings.append({
            "code": "NO_RULES_FOUND",
            "message": "No structured submission rules could be extracted from the guidelines.",
        })
        return {
            "schemaVersion": 1,
            "rules": {"schemaVersion": 1},
            "fields": {},
            "alternatives": [],
        }, warnings, token_usage

    # 2. Group findings by (path, articleType)
    grouped: dict[tuple[str, str | None], list[Finding]] = {}
    for f in valid_findings:
        key = (f.path, f.articleType.lower() if f.articleType else None)
        grouped.setdefault(key, []).append(f)

    # 3. Merge / Conflict resolution
    resolved_fields: dict[tuple[str, str | None], Finding] = {}
    alternatives: list[dict[str, Any]] = []

    for key, f_list in grouped.items():
        path, art_type = key

        # If list field, take union of values (GE-MRG-05)
        if path in LIST_PATHS:
            union_vals: list[Any] = []
            seen = set()
            best_confidence = "low"
            best_evidence = ""
            for item in f_list:
                c_rank = CONFIDENCE_ORDER.get(item.confidence, 1)
                if c_rank > CONFIDENCE_ORDER.get(best_confidence, 1):
                    best_confidence = item.confidence
                    best_evidence = item.evidence
                vals = item.value if isinstance(item.value, list) else [item.value]
                for v in vals:
                    v_key = str(v).lower()
                    if v_key not in seen:
                        seen.add(v_key)
                        union_vals.append(v)
            
            resolved_fields[key] = Finding(
                path=path,
                value=union_vals,
                evidence=best_evidence,
                articleType=f_list[0].articleType,
                confidence=best_confidence,
            )
            continue

        # For scalar fields: check if all values identical
        first_val = f_list[0].value
        all_same = all(f.value == first_val for f in f_list)

        if all_same:
            # Merge: pick highest confidence (GE-MRG-02)
            f_list.sort(key=lambda x: CONFIDENCE_ORDER.get(x.confidence, 1), reverse=True)
            resolved_fields[key] = f_list[0]
        else:
            # CONFLICT: different values for same path & scope (GE-MRG-03, GE-MRG-06)
            # Pick winner deterministically: highest confidence, then first
            f_list.sort(key=lambda x: CONFIDENCE_ORDER.get(x.confidence, 1), reverse=True)
            winner = f_list[0]
            resolved_fields[key] = winner

            candidates = [
                {"value": cand.value, "evidence": cand.evidence, "confidence": cand.confidence}
                for cand in f_list
            ]
            alternatives.append({
                "path": path,
                "articleType": winner.articleType,
                "winner": winner.value,
                "candidates": candidates,
            })
            warnings.append({
                "code": "CONFLICT",
                "message": f"Conflicting values extracted for '{path}'. Selected {winner.value}.",
                "path": path,
            })

    # 4. Assemble into rules dictionary
    rules_dict: dict[str, Any] = {"schemaVersion": 1}
    fields_provenance: dict[str, Any] = {}
    article_types_dict: dict[str, dict[str, Any]] = {}

    for (path, _), finding in resolved_fields.items():
        prov_key = f"{finding.articleType}:{path}" if finding.articleType else path
        fields_provenance[prov_key] = {
            "evidence": finding.evidence,
            "confidence": finding.confidence,
            "articleType": finding.articleType,
            "edited": False,
        }

        # If scoped to an article type
        if finding.articleType:
            at_name = finding.articleType
            if at_name not in article_types_dict:
                article_types_dict[at_name] = {"name": at_name}
            prop_name = path.split(".")[-1]
            article_types_dict[at_name][prop_name] = finding.value
        else:
            # Global rule path like "general.maxWords" or "citation.style"
            parts = path.split(".")
            if len(parts) == 2:
                section, key = parts
                rules_dict.setdefault(section, {})[key] = finding.value
            elif len(parts) == 3:
                section, sub, key = parts
                rules_dict.setdefault(section, {}).setdefault(sub, {})[key] = finding.value
            else:
                rules_dict[path] = finding.value

    # Assemble articleTypes list
    if article_types_dict:
        types_list = list(article_types_dict.values())
        rules_dict["articleTypes"] = types_list
        if len(types_list) > 1:
            warnings.append({
                "code": "ARTICLE_TYPES_DETECTED",
                "message": f"Detected {len(types_list)} article types in guidelines.",
            })
        
        # Propose Research Article or Original Article as default (GE-MRG-08)
        for at in types_list:
            at_low = at["name"].lower()
            if "research" in at_low or "original" in at_low:
                rules_dict["defaultArticleType"] = at["name"]
                break
        if "defaultArticleType" not in rules_dict and types_list:
            rules_dict["defaultArticleType"] = types_list[0]["name"]

    # Cross-field checks (GE-MRG-09, GE-SCH-10)
    general = rules_dict.get("general", {})
    min_w = general.get("minWords")
    max_w = general.get("maxWords")
    if min_w is not None and max_w is not None and min_w > max_w:
        warnings.append({
            "code": "INVALID_WORD_RANGE",
            "message": f"minWords ({min_w}) is greater than maxWords ({max_w}).",
            "path": "general.minWords",
        })
        # Remove minWords or preserve for user review
        general.pop("minWords", None)

    max_abs = general.get("maxAbstractWords")
    if max_abs is not None and max_w is not None and max_abs > max_w:
        warnings.append({
            "code": "ABSTRACT_EXCEEDS_MANUSCRIPT",
            "message": "Abstract word limit is greater than the total manuscript limit.",
            "path": "general.maxAbstractWords",
        })

    # Validate final schema (strict validation)
    try:
        validated_schema = GuidelineRuleSchema.model_validate(rules_dict)
        final_rules = validated_schema.model_dump(exclude_none=True)
    except Exception as e:
        warnings.append({
            "code": "SCHEMA_VALIDATION_ERROR",
            "message": f"Rule set schema validation error: {e}",
        })
        final_rules = rules_dict

    draft = {
        "schemaVersion": 1,
        "rules": final_rules,
        "fields": fields_provenance,
        "alternatives": alternatives,
    }

    return draft, warnings, token_usage


class PipelineResult:
    def __init__(self, draft: dict[str, Any], warnings: list[dict[str, str]], input_tokens: int = 0, output_tokens: int = 0):
        self.draft = draft
        self.warnings = warnings
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


async def run_extraction_pipeline(
    raw_text: str,
    is_html: bool = False,
    client: BaseLLMClient | None = None,
) -> PipelineResult:
    """End-to-end extraction pipeline helper for evaluation and direct processing."""
    from app.services.guidelines.cleaner import clean_guideline_content
    from app.services.guidelines.chunker import build_text_chunks
    from app.services.guidelines.llm.gemini_client import GeminiLLMClient

    if client is None:
        client = GeminiLLMClient()

    cleaned_text, _, _ = clean_guideline_content(raw_text, is_html=is_html)
    chunks, _ = build_text_chunks(cleaned_text)
    draft, warnings, tokens = await orchestrate_extraction(chunks, client, source_text=cleaned_text)
    return PipelineResult(
        draft=draft,
        warnings=warnings,
        input_tokens=tokens.get("input_tokens", 0),
        output_tokens=tokens.get("output_tokens", 0),
    )


