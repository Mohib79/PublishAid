from typing import Any
from pydantic import BaseModel, ConfigDict, model_validator
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
