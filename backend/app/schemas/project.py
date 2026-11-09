from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ManuscriptInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    file_name: str
    size_bytes: int
    uploaded_at: datetime
    available: bool
    expires_at: datetime


class TargetJournalInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    title: str
    publisher: str


class ProjectCounts(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    conversions: int = 0
    compliance_reports: int = 0


class ActivityItemOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    project_id: Optional[str] = None
    project_title: Optional[str] = None
    event_type: str
    details: dict[str, Any] = Field(default_factory=dict)
    journal_title: Optional[str] = None
    created_at: datetime


class ProjectCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str
    research_field: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[Any] = None


class ProjectPatch(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: Optional[str] = None
    research_field: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[Any] = None
    status: Optional[str] = None


class ProjectItemOut(BaseModel):
    """Standard project schema returned on create, patch, etc."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

    id: str
    title: str
    research_field: Optional[str] = None
    field: str = ""  # Backward compatibility for frontend binding
    abstract: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    manuscript: Optional[ManuscriptInfo] = None


class ProjectListItemOut(BaseModel):
    """Light item in list response."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    title: str
    research_field: Optional[str] = None
    field: str = ""
    status: str
    created_at: datetime
    updated_at: datetime
    shortlisted_count: int = 0
    has_manuscript: bool = False
    target_journal_title: Optional[str] = None


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[ProjectListItemOut]
    total: int
    page: int
    page_size: int


class ProjectOverviewOut(BaseModel):
    """Workspace overview response with counts and recent activity."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    title: str
    research_field: Optional[str] = None
    field: str = ""
    abstract: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    manuscript: Optional[ManuscriptInfo] = None
    shortlisted_count: int = 0
    target_journal: Optional[TargetJournalInfo] = None
    counts: ProjectCounts = Field(default_factory=ProjectCounts)
    recent_activity: list[ActivityItemOut] = Field(default_factory=list)


# Backward compatibility for existing endpoints
class ProjectOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

    id: str
    title: str
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    field: str = ""
    target_journal_id: Optional[str] = None
    target_journal_title: Optional[str] = None
    status: str = "draft"
    updated_at: str = ""
    word_count: int = 0
    file_name: Optional[str] = None
    file_size: Optional[str] = None


class ShortlistBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    similarity_score: Optional[float] = None
