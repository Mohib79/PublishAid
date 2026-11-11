"""
Base LLM client interface and findings data models for Guideline Extraction.
Reference: Guideline Extraction Plan Section 7.3, 10.9 (GE-LLM).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Literal

WHITELISTED_PATHS = {
    # General
    "general.maxWords",
    "general.minWords",
    "general.wordLimitExcludes",
    "general.maxAbstractWords",
    "general.abstractStructure",
    "general.keywords.min",
    "general.keywords.max",
    "general.maxTitleChars",
    "general.requiredSections",
    "general.requiredStatements",
    # Citation
    "citation.style",
    "citation.numbered",
    "citation.maxReferences",
    "citation.notes",
    # Layout
    "layout.columns",
    "layout.pageSize",
    "layout.fontFamily",
    "layout.fontSizePt",
    "layout.lineSpacing",
    "layout.marginsCm.top",
    "layout.marginsCm.bottom",
    "layout.marginsCm.left",
    "layout.marginsCm.right",
    "layout.maxPages",
    # Figures
    "figures.maxFigures",
    "figures.maxTables",
    "figures.formats",
    "figures.minDpi",
    # Submission
    "submission.fileFormats",
    "submission.reviewType",
    "submission.templateUrl",
    "submission.coverLetterRequired",
    "submission.highlightsRequired",
    # Article Types
    "articleTypes",
    "defaultArticleType",
    "other",
    # Scoped Article Type paths (when articleType is specified)
    "maxWords",
    "maxAbstractWords",
    "requiredSections",
    "maxFigures",
    "maxTables",
    "maxReferences",
    "notes",
}


@dataclass
class Finding:
    path: str
    value: Any
    evidence: str
    articleType: str | None = None
    confidence: Literal["high", "medium", "low"] = "low"


@dataclass
class LLMExtractResult:
    findings: list[Finding]
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = ""
    prompt_version: str = "v1"
    raw_response: str | None = None


class LLMError(Exception):
    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    async def extract_findings(
        self,
        chunk_text: str,
        heading_path: str = "",
        repair_context: str | None = None,
    ) -> LLMExtractResult:
        """
        Extracts findings from a guideline chunk.
        """
        pass

