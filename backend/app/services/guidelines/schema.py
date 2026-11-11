from __future__ import annotations
import re
from typing import Any, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationInfo,
)

# ---------------------------------------------------------------------------
# Canonical Vocabularies & Normalization Mappings
# ---------------------------------------------------------------------------

CANONICAL_SECTIONS = [
    "Abstract",
    "Keywords",
    "Introduction",
    "Background",
    "Methods",
    "Results",
    "Discussion",
    "Conclusion",
    "Acknowledgements",
    "References",
    "Appendix",
    "Data Availability",
    "Funding",
    "Conflict of Interest",
    "Author Contributions",
]

SECTION_SYNONYMS: dict[str, str] = {
    "materials and methods": "Methods",
    "material and methods": "Methods",
    "methodology": "Methods",
    "method": "Methods",
    "methods and materials": "Methods",
    "experimental methods": "Methods",
    "experimental procedures": "Methods",
    "materials & methods": "Methods",
    "results and discussion": "Results",
    "conclusions": "Conclusion",
    "concluding remarks": "Conclusion",
    "references and notes": "References",
    "bibliography": "References",
    "literature cited": "References",
    "appendices": "Appendix",
    "supplementary material": "Appendix",
    "supplementary information": "Appendix",
    "conflicts of interest": "Conflict of Interest",
    "competing interests": "Conflict of Interest",
    "declaration of competing interest": "Conflict of Interest",
    "declaration of interest": "Conflict of Interest",
    "data availability statement": "Data Availability",
    "availability of data and materials": "Data Availability",
    "funding statement": "Funding",
    "financial support": "Funding",
    "author contribution": "Author Contributions",
    "authors' contributions": "Author Contributions",
    "acknowledgments": "Acknowledgements",
    "acknowledgement": "Acknowledgements",
}

CITATION_STYLE_ALIASES: dict[str, str] = {
    "ieee": "IEEE",
    "ieee style": "IEEE",
    "ieee reference style": "IEEE",
    "numbered": "IEEE",
    "vancouver": "Vancouver",
    "vancouver style": "Vancouver",
    "apa": "APA",
    "apa 7": "APA",
    "apa 7th edition": "APA",
    "apa style": "APA",
    "harvard": "Harvard",
    "harvard style": "Harvard",
    "harvard (elsevier)": "Harvard",
    "mla": "MLA",
    "mla style": "MLA",
    "chicago": "Chicago",
    "chicago style": "Chicago",
    "chicago author-date": "Chicago",
    "acm": "ACM",
    "acm style": "ACM",
    "springer": "Springer",
    "springer basic": "Springer",
    "nature": "Nature",
    "elsevier": "Elsevier",
    "acs": "ACS",
    "ama": "AMA",
}

LAYOUT_COLUMN_ALIASES: dict[str, str] = {
    "single": "single",
    "one column": "single",
    "1-col": "single",
    "1 column": "single",
    "double": "double",
    "two-column": "double",
    "two column": "double",
    "double column": "double",
    "2-col": "double",
    "2 column": "double",
    "either": "either",
}

# HTML tag stripper regex
HTML_TAG_RE = re.compile(r"<[^>]+>")
# Control character regex (excluding standard newlines, tabs, and carriage returns)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def clean_string(val: str | None) -> str | None:
    if val is None:
        return None
    # Strip HTML tags
    cleaned = HTML_TAG_RE.sub(" ", val)
    # Remove control characters
    cleaned = CONTROL_CHAR_RE.sub("", cleaned)
    # Collapse multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_integer_value(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError("Boolean value is not a valid integer")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not v.is_integer():
            raise ValueError(f"Value {v} is a non-integer float")
        return int(v)
    if isinstance(v, str):
        # normalize "8,000", "8 000", "8000.0"
        s = v.replace(",", "").replace(" ", "").strip()
        try:
            val_f = float(s)
            if not val_f.is_integer():
                raise ValueError(f"String '{v}' contains a non-integer number")
            return int(val_f)
        except ValueError:
            raise ValueError(f"Cannot parse '{v}' as an integer")
    raise ValueError(f"Unsupported type {type(v)} for integer")


def normalize_float_value(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError("Boolean value is not a valid number")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(",", "").replace(" ", "").strip()
        try:
            return float(s)
        except ValueError:
            raise ValueError(f"Cannot parse '{v}' as a number")
    raise ValueError(f"Unsupported type {type(v)} for number")


SECTION_PREFIX_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*|[A-Za-z]|[IVXLCDMivxlcdm]+)(?:[\.\:\)\-–—]\s*|\s+))\s*"
)


def canonicalize_section_name(raw: str) -> str:
    cleaned = clean_string(raw) or ""
    # Strip leading numbers/enumeration like "1. ", "2.1 ", "II. ", "A. "
    stripped = SECTION_PREFIX_RE.sub("", cleaned).strip()
    key = stripped.lower()
    if key in SECTION_SYNONYMS:
        return SECTION_SYNONYMS[key]
    for canon in CANONICAL_SECTIONS:
        if canon.lower() == key:
            return canon
    return stripped if stripped else cleaned


# ---------------------------------------------------------------------------
# Pydantic Sub-Models
# ---------------------------------------------------------------------------

class StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KeywordsSpec(StrictBase):
    min: int | None = Field(default=None, ge=0, le=30)
    max: int | None = Field(default=None, ge=1, le=30)

    @field_validator("min", "max", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @model_validator(mode="after")
    def _validate_min_le_max(self) -> KeywordsSpec:
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError("keywords.min must be at most keywords.max")
        return self


WordLimitExcludesEnum = Literal[
    "abstract",
    "references",
    "tables",
    "figureCaptions",
    "footnotes",
    "appendices",
    "acknowledgements",
    "title",
    "keywords",
]

RequiredStatementsEnum = Literal[
    "ethics",
    "conflictOfInterest",
    "dataAvailability",
    "funding",
    "authorContributions",
    "acknowledgements",
]


class GeneralRules(StrictBase):
    maxWords: int | None = Field(default=None, ge=100, le=100000)
    minWords: int | None = Field(default=None, ge=0, le=100000)
    wordLimitExcludes: list[WordLimitExcludesEnum] | None = None
    maxAbstractWords: int | None = Field(default=None, ge=20, le=1000)
    abstractStructure: Literal["structured", "unstructured"] | None = None
    keywords: KeywordsSpec | None = None
    maxTitleChars: int | None = Field(default=None, ge=10, le=500)
    requiredSections: list[str] | None = Field(default=None, max_length=30)
    requiredStatements: list[RequiredStatementsEnum] | None = None

    @field_validator("maxWords", "minWords", "maxAbstractWords", "maxTitleChars", mode="before")
    @classmethod
    def _coerce_ints(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @field_validator("wordLimitExcludes", mode="before")
    @classmethod
    def _dedup_excludes(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("wordLimitExcludes must be a list")
        seen = set()
        out = []
        for item in v:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @field_validator("requiredSections", mode="before")
    @classmethod
    def _normalize_sections(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("requiredSections must be a list")
        seen = set()
        out = []
        for raw in v:
            canon = canonicalize_section_name(str(raw))
            if canon and canon not in seen:
                seen.add(canon)
                out.append(canon)
        return out

    @field_validator("requiredStatements", mode="before")
    @classmethod
    def _dedup_statements(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("requiredStatements must be a list")
        seen = set()
        out = []
        for item in v:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @model_validator(mode="after")
    def _validate_words_range(self) -> GeneralRules:
        if self.minWords is not None and self.maxWords is not None:
            if self.minWords > self.maxWords:
                raise ValueError("minWords must be at most maxWords")
        return self


CitationStyleEnum = Literal[
    "IEEE",
    "APA",
    "Vancouver",
    "Harvard",
    "MLA",
    "Chicago",
    "ACM",
    "Springer",
    "Nature",
    "Elsevier",
    "ACS",
    "AMA",
    "Other",
]


class CitationRules(StrictBase):
    style: CitationStyleEnum | None = None
    numbered: bool | None = None
    maxReferences: int | None = Field(default=None, ge=1, le=1000)
    notes: str | None = Field(default=None, max_length=300)

    @field_validator("maxReferences", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @model_validator(mode="before")
    @classmethod
    def _map_citation_style_and_notes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_style = data.get("style")
            if raw_style is not None:
                s = clean_string(str(raw_style)) or ""
                s_lower = s.lower()
                if s_lower in CITATION_STYLE_ALIASES:
                    data["style"] = CITATION_STYLE_ALIASES[s_lower]
                else:
                    found = False
                    for item in [
                        "IEEE", "APA", "Vancouver", "Harvard", "MLA", "Chicago",
                        "ACM", "Springer", "Nature", "Elsevier", "ACS", "AMA", "Other",
                    ]:
                        if item.lower() == s_lower:
                            data["style"] = item
                            found = True
                            break
                    if not found and s:
                        data["style"] = "Other"
                        existing_notes = data.get("notes")
                        if existing_notes:
                            data["notes"] = f"{existing_notes}; Style: {s}"[:300]
                        else:
                            data["notes"] = s[:300]
        return data

    @field_validator("notes", mode="before")
    @classmethod
    def _clean_notes(cls, v: Any) -> str | None:
        return clean_string(v)


class MarginsCm(StrictBase):
    top: float | None = Field(default=None, ge=0.5, le=6.0)
    bottom: float | None = Field(default=None, ge=0.5, le=6.0)
    left: float | None = Field(default=None, ge=0.5, le=6.0)
    right: float | None = Field(default=None, ge=0.5, le=6.0)

    @field_validator("top", "bottom", "left", "right", mode="before")
    @classmethod
    def _coerce_margin(cls, v: Any) -> float | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip().lower()
            if s.endswith("in") or s.endswith("inch") or s.endswith("inches") or s.endswith('"'):
                num = float(re.sub(r"[^\d.]", "", s))
                return round(num * 2.54, 2)
            if s.endswith("mm"):
                num = float(re.sub(r"[^\d.]", "", s))
                return round(num / 10.0, 2)
            if s.endswith("cm"):
                num = float(re.sub(r"[^\d.]", "", s))
                return round(num, 2)
        return normalize_float_value(v)


LayoutColumnsEnum = Literal["single", "double", "either"]
PageSizeEnum = Literal["A4", "Letter", "either"]


class LayoutRules(StrictBase):
    columns: LayoutColumnsEnum | None = None
    pageSize: PageSizeEnum | None = None
    fontFamily: str | None = Field(default=None, max_length=80)
    fontSizePt: float | None = Field(default=None, ge=6.0, le=24.0)
    lineSpacing: float | None = Field(default=None, ge=1.0, le=3.0)
    marginsCm: MarginsCm | None = None
    maxPages: int | None = Field(default=None, ge=1, le=200)

    @field_validator("columns", mode="before")
    @classmethod
    def _map_columns(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = clean_string(str(v)) or ""
        s_lower = s.lower()
        if s_lower in LAYOUT_COLUMN_ALIASES:
            return LAYOUT_COLUMN_ALIASES[s_lower]
        return s

    @field_validator("maxPages", mode="before")
    @classmethod
    def _coerce_pages(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @field_validator("fontSizePt", "lineSpacing", mode="before")
    @classmethod
    def _coerce_floats(cls, v: Any) -> float | None:
        return normalize_float_value(v)

    @field_validator("fontFamily", mode="before")
    @classmethod
    def _clean_font(cls, v: Any) -> str | None:
        return clean_string(v)


FigureFormatEnum = Literal["tiff", "eps", "png", "jpg", "pdf", "svg"]


class FiguresRules(StrictBase):
    maxFigures: int | None = Field(default=None, ge=0, le=200)
    maxTables: int | None = Field(default=None, ge=0, le=200)
    formats: list[FigureFormatEnum] | None = None
    minDpi: int | None = Field(default=None, ge=72, le=1200)

    @field_validator("maxFigures", "maxTables", "minDpi", mode="before")
    @classmethod
    def _coerce_ints(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @field_validator("formats", mode="before")
    @classmethod
    def _dedup_formats(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("formats must be a list")
        seen = set()
        out = []
        for item in v:
            item_clean = str(item).lower().strip()
            if item_clean == "jpeg":
                item_clean = "jpg"
            if item_clean not in seen:
                seen.add(item_clean)
                out.append(item_clean)
        return out


SubmissionFileFormatEnum = Literal["docx", "tex", "pdf", "rtf", "txt"]
ReviewTypeEnum = Literal["single_blind", "double_blind", "open"]


class SubmissionRules(StrictBase):
    fileFormats: list[SubmissionFileFormatEnum] | None = None
    reviewType: ReviewTypeEnum | None = None
    templateUrl: str | None = Field(default=None, max_length=500)
    coverLetterRequired: bool | None = None
    highlightsRequired: bool | None = None

    @field_validator("templateUrl", mode="before")
    @classmethod
    def _validate_template_url(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = clean_string(str(v)) or ""
        if not s.startswith("https://"):
            raise ValueError("templateUrl must be a valid https URL")
        return s

    @field_validator("fileFormats", mode="before")
    @classmethod
    def _dedup_formats(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("fileFormats must be a list")
        seen = set()
        out = []
        for item in v:
            c = str(item).lower().strip()
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out


class ArticleTypeSpec(StrictBase):
    name: str = Field(min_length=1, max_length=80)
    maxWords: int | None = Field(default=None, ge=100, le=100000)
    maxAbstractWords: int | None = Field(default=None, ge=20, le=1000)
    requiredSections: list[str] | None = Field(default=None, max_length=30)
    maxFigures: int | None = Field(default=None, ge=0, le=200)
    maxTables: int | None = Field(default=None, ge=0, le=200)
    maxReferences: int | None = Field(default=None, ge=1, le=1000)
    notes: str | None = Field(default=None, max_length=300)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> str:
        s = clean_string(str(v)) if v is not None else ""
        if not s:
            raise ValueError("articleType name cannot be empty")
        return s

    @field_validator("maxWords", "maxAbstractWords", "maxFigures", "maxTables", "maxReferences", mode="before")
    @classmethod
    def _coerce_ints(cls, v: Any) -> int | None:
        return normalize_integer_value(v)

    @field_validator("requiredSections", mode="before")
    @classmethod
    def _canon_sections(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("requiredSections must be a list")
        seen = set()
        out = []
        for raw in v:
            canon = canonicalize_section_name(str(raw))
            if canon and canon not in seen:
                seen.add(canon)
                out.append(canon)
        return out

    @field_validator("notes", mode="before")
    @classmethod
    def _clean_notes(cls, v: Any) -> str | None:
        return clean_string(v)


class OtherNote(StrictBase):
    label: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("label", "text", mode="before")
    @classmethod
    def _clean_text(cls, v: Any) -> str:
        s = clean_string(str(v)) if v is not None else ""
        if not s:
            raise ValueError("label and text must not be empty")
        return s


# ---------------------------------------------------------------------------
# Top-Level Guideline Rule Model (Version 1 Contract)
# ---------------------------------------------------------------------------

class GuidelineRuleSchema(StrictBase):
    schemaVersion: Literal[1] = 1
    general: GeneralRules | None = None
    citation: CitationRules | None = None
    layout: LayoutRules | None = None
    figures: FiguresRules | None = None
    submission: SubmissionRules | None = None
    articleTypes: list[ArticleTypeSpec] | None = Field(default=None, max_length=15)
    defaultArticleType: str | None = None
    other: list[OtherNote] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _validate_article_types_and_defaults(self) -> GuidelineRuleSchema:
        if self.articleTypes:
            names = [at.name.lower() for at in self.articleTypes]
            if len(names) != len(set(names)):
                raise ValueError("articleTypes names must be unique (case-insensitive)")
            if self.defaultArticleType is not None:
                matches = [at.name for at in self.articleTypes if at.name.lower() == self.defaultArticleType.lower()]
                if not matches:
                    raise ValueError(f"defaultArticleType '{self.defaultArticleType}' must match an articleType name")
                # Normalize case to match
                self.defaultArticleType = matches[0]
        else:
            if self.defaultArticleType is not None:
                raise ValueError("defaultArticleType cannot be set when articleTypes is empty")
        return self


# ---------------------------------------------------------------------------
# Schema Metadata Provider (for GET /guidelines/schema)
# ---------------------------------------------------------------------------

def get_schema_metadata() -> dict[str, Any]:
    """
    Returns structured definitions for frontend dynamic form generation,
    allowed enums, canonical sections, and valid numerical ranges.
    """
    return {
        "schemaVersion": 1,
        "canonicalSections": CANONICAL_SECTIONS,
        "sectionSynonyms": SECTION_SYNONYMS,
        "enums": {
            "wordLimitExcludes": [
                "abstract", "references", "tables", "figureCaptions",
                "footnotes", "appendices", "acknowledgements", "title", "keywords"
            ],
            "requiredStatements": [
                "ethics", "conflictOfInterest", "dataAvailability",
                "funding", "authorContributions", "acknowledgements"
            ],
            "citationStyles": [
                "IEEE", "APA", "Vancouver", "Harvard", "MLA", "Chicago",
                "ACM", "Springer", "Nature", "Elsevier", "ACS", "AMA", "Other"
            ],
            "layoutColumns": ["single", "double", "either"],
            "pageSizes": ["A4", "Letter", "either"],
            "figureFormats": ["tiff", "eps", "png", "jpg", "pdf", "svg"],
            "submissionFileFormats": ["docx", "tex", "pdf", "rtf", "txt"],
            "reviewTypes": ["single_blind", "double_blind", "open"],
            "abstractStructure": ["structured", "unstructured"],
        },
        "ranges": {
            "general.maxWords": {"min": 100, "max": 100000},
            "general.minWords": {"min": 0, "max": 100000},
            "general.maxAbstractWords": {"min": 20, "max": 1000},
            "general.keywords.min": {"min": 0, "max": 30},
            "general.keywords.max": {"min": 1, "max": 30},
            "general.maxTitleChars": {"min": 10, "max": 500},
            "citation.maxReferences": {"min": 1, "max": 1000},
            "layout.fontSizePt": {"min": 6.0, "max": 24.0},
            "layout.lineSpacing": {"min": 1.0, "max": 3.0},
            "layout.marginsCm": {"min": 0.5, "max": 6.0},
            "layout.maxPages": {"min": 1, "max": 200},
            "figures.maxFigures": {"min": 0, "max": 200},
            "figures.maxTables": {"min": 0, "max": 200},
            "figures.minDpi": {"min": 72, "max": 1200},
        },
    }
