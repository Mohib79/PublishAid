from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.journal import Journal
    from app.db.models.guideline_rule import GuidelineRule

class ConversionJob(Base):
    __tablename__ = "conversion_jobs"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversion_type: Mapped[str] = mapped_column(
        Enum(
            "format_conversion",
            "manuscript_transformation",
            native_enum=False,
            create_constraint=True,
            name="ck_conversion_jobs_conversion_type",
        ),
        nullable=False,
    )
    source_format: Mapped[str | None] = mapped_column(
        Enum("docx", "tex", native_enum=False, create_constraint=True, name="ck_conversion_jobs_source_format"),
        nullable=True,
    )
    target_format: Mapped[str | None] = mapped_column(
        Enum("docx", "tex", native_enum=False, create_constraint=True, name="ck_conversion_jobs_target_format"),
        nullable=True,
    )
    source_journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    target_journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    target_guideline_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_rules.rule_id", ondelete="SET NULL"),
        nullable=True,
    )
    conversion_status: Mapped[str] = mapped_column(
        Enum("pending", "completed", "failed", native_enum=False, create_constraint=True, name="ck_conversion_jobs_status"),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    output_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship("Project", back_populates="conversion_jobs")
    source_journal: Mapped[Journal | None] = relationship("Journal", foreign_keys=[source_journal_id])
    target_journal: Mapped[Journal | None] = relationship("Journal", foreign_keys=[target_journal_id])
    guideline_rule: Mapped[GuidelineRule | None] = relationship(
        "GuidelineRule",
        foreign_keys=[target_guideline_id],
        back_populates="conversion_jobs",
    )
