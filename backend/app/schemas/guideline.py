"""
Pydantic Schemas for Guideline Extraction & Rule Sets.
Reference: Guideline Extraction Plan Section 6.1, 6.2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateExtractionRequest(BaseSchema):
    source_type: Literal["url", "text"]
    url: str | None = None
    text: str | None = None
    journal_id: str | None = None
    project_id: str | None = None

    @model_validator(mode="after")
    def _validate_source_mutual_exclusivity(self) -> CreateExtractionRequest:
        if self.source_type == "url":
            if not self.url or not self.url.strip():
                raise ValueError("url field is required when sourceType is 'url'")
            if self.text is not None and self.text.strip():
                raise ValueError("text field cannot be provided when sourceType is 'url'")
        elif self.source_type == "text":
            if not self.text or not self.text.strip():
                raise ValueError("text field is required when sourceType is 'text'")
            if self.url is not None and self.url.strip():
                raise ValueError("url field cannot be provided when sourceType is 'text'")
            # Text length checks (GE-API-05, GE-API-06)
            words = len(self.text.split())
            if words < 30:
                raise ValueError(f"Guideline text is too short ({words} words). Minimum 30 words required.")
            if len(self.text) > 200000:
                raise ValueError(f"Guideline text exceeds maximum length of 200,000 characters.")
        return self


class SourceMetadata(BaseSchema):
    title: str | None = None
    word_count: int = 0
    language: str = "en"
    truncated: bool = False


class ExtractionWarning(BaseSchema):
    code: str
    message: str
    path: str | None = None


class ExtractionError(BaseSchema):
    code: str
    message: str


class ExtractionJobOut(BaseSchema):
    id: str
    status: str
    step: str
    cached: bool = False
    source_type: str
    source_url: str | None = None
    final_url: str | None = None
    journal_id: str | None = None
    project_id: str | None = None
    source: SourceMetadata | None = None
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    draft: dict[str, Any] | None = None
    error: ExtractionError | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExtractionListOut(BaseSchema):
    items: list[ExtractionJobOut]
    total: int
    page: int
    page_size: int


class ConfirmExtractionRequest(BaseSchema):
    rules: dict[str, Any]
    name: str | None = None
    journal_id: str | None = None
    project_id: str | None = None
    acknowledged_fields: list[str] = Field(default_factory=list)


class RuleSetCreateRequest(BaseSchema):
    name: str
    rules: dict[str, Any]
    journal_id: str | None = None
    source_url: str | None = None


class RuleSetPatchRequest(BaseSchema):
    name: str | None = None
    rules: dict[str, Any] | None = None


class RuleSetOut(BaseSchema):
    id: str
    name: str
    journal_id: str | None = None
    journal_title: str | None = None
    origin: str
    version: int
    is_active: bool
    is_system: bool
    schema_version: int
    rules: dict[str, Any]
    provenance: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None
    lineage_id: str
    created_at: datetime
    updated_at: datetime | None = None


class RuleSetListOut(BaseSchema):
    items: list[RuleSetOut]
    total: int
    page: int
    page_size: int


class JournalEffectiveRulesOut(BaseSchema):
    rule_set: RuleSetOut | None = None
    source: str | None = None  # "user", "system", or None

