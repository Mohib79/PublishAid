from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ProjectCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=300)
    abstract: Optional[str] = ""
    keywords: Optional[list[str]] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Title cannot be empty or blank")
        return s


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    abstract: Optional[str] = None
    keywords: Optional[list[str]] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Title cannot be empty or blank")
            return s
        return v


class ProjectOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    title: str
    abstract: str
    keywords: list[str] = Field(default_factory=list)
    field: str = ""
    target_journal_id: Optional[str] = None
    target_journal_title: Optional[str] = None
    status: str = "Draft"
    updated_at: str
    word_count: int = 0
    file_name: Optional[str] = None
    file_size: Optional[str] = None


class ShortlistBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    similarity_score: Optional[float] = None
