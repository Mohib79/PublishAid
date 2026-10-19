from typing import Any, Optional, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class JournalItemOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    title: str
    publisher: str
    issn: str | None = None
    subject_category: str | None = None
    cite_score: float | None = None
    impact_factor: float | None = None
    quartile: str | None = None
    aims_and_scope: str
    open_access_type: str | None = None
    review_weeks: int | None = None
    acceptance_rate: float | None = None

    @model_validator(mode="before")
    @classmethod
    def map_journal_attributes(cls, data: Any) -> Any:
        if hasattr(data, "journal_id"):
            return {
                "id": str(data.journal_id),
                "title": data.journal_title,
                "publisher": data.publisher,
                "issn": data.issn,
                "subjectCategory": data.subject_category,
                "citeScore": data.citescore,
                "impactFactor": data.impact_factor,
                "quartile": data.quartile,
                "aimsAndScope": data.aims_and_scope,
                "openAccessType": data.open_access_type,
                "reviewWeeks": data.review_weeks,
                "acceptanceRate": data.acceptance_rate,
            }
        if isinstance(data, dict):
            mapped = dict(data)
            if "journal_id" in mapped and "id" not in mapped:
                mapped["id"] = str(mapped["journal_id"])
            if "journal_title" in mapped and "title" not in mapped:
                mapped["title"] = mapped["journal_title"]
            if "citescore" in mapped and "citeScore" not in mapped:
                mapped["citeScore"] = mapped["citescore"]
            return mapped
        return data


class MatchJournalItemOut(JournalItemOut):
    match_score: int
    raw_similarity: float
    match_tag: Optional[str] = None
    is_shortlisted: bool = False


class MatchMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    model: str
    took_ms: int
    total_journals: int


class MatchResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    results: list[MatchJournalItemOut]
    meta: MatchMeta


class MatchRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    title: Optional[str] = Field(None, max_length=300)
    abstract: Optional[str] = Field(None, max_length=10000)
    keywords: Optional[Union[list[str], str]] = None
    limit: int = Field(20, ge=1, le=50)
    project_id: Optional[Union[int, str]] = None

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()][:20]
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    res.append(item.strip())
            return res[:20]
        return []

    @model_validator(mode="after")
    def validate_content_presence(self) -> "MatchRequest":
        clean_title = (self.title or "").strip()
        clean_abstract = (self.abstract or "").strip()
        if not clean_title and not clean_abstract:
            raise ValueError("At least one of 'title' or 'abstract' must be provided.")
        return self


class JournalBrowseResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    items: list[JournalItemOut]
    total: int
    page: int
    limit: int
    total_pages: int
    categories: list[str]
    publishers: list[str]
