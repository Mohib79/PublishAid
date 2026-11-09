from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    DateTime,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.project_journal import ProjectJournal
    from app.db.models.conversion_job import ConversionJob
    from app.db.models.compliance_report import ComplianceReport

class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    project_title: Mapped[str] = mapped_column(String(300), nullable=False)
    research_field: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )
    manuscript_abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    current_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manuscript_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manuscript_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    manuscript_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship("User", back_populates="projects")
    project_journals: Mapped[list[ProjectJournal]] = relationship(
        "ProjectJournal",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conversion_jobs: Mapped[list[ConversionJob]] = relationship(
        "ConversionJob",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    compliance_reports: Mapped[list[ComplianceReport]] = relationship(
        "ComplianceReport",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("char_length(btrim(project_title)) > 0", name="ck_projects_non_empty_title"),
        CheckConstraint("status IN ('draft', 'in_progress', 'ready_to_submit', 'submitted')", name="ck_projects_valid_status"),
        CheckConstraint("manuscript_size_bytes IS NULL OR manuscript_size_bytes >= 0", name="ck_projects_manuscript_size_non_negative"),
        Index("ix_projects_user_updated", "user_id", text("updated_at DESC")),
        Index("ix_projects_user_status", "user_id", "status"),
    )
