from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func, text
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
        index=True,
    )
    project_title: Mapped[str] = mapped_column(String(300), nullable=False)
    manuscript_abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    current_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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
