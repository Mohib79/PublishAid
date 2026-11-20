from __future__ import annotations
from typing import TYPE_CHECKING, Any
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.project import Project
    from app.db.models.journal import Journal
    from app.db.models.guideline_rule import GuidelineRule


class GuidelineExtraction(Base):
    __tablename__ = "guideline_extractions"

    extraction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    step: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_called: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    cached: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    confirmed_rule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_rules.rule_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="guideline_extractions")
    project: Mapped[Project | None] = relationship("Project", backref="guideline_extractions")
    journal: Mapped[Journal | None] = relationship("Journal", backref="guideline_extractions")
    confirmed_rule: Mapped[GuidelineRule | None] = relationship("GuidelineRule", foreign_keys=[confirmed_rule_id])

    __table_args__ = (
        CheckConstraint("source_type IN ('url', 'text')", name="ck_guideline_extractions_source_type"),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name="ck_guideline_extractions_status"),
        CheckConstraint("step IN ('queued', 'fetching', 'cleaning', 'extracting', 'validating', 'done')", name="ck_guideline_extractions_step"),
        CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0)", name="ck_guideline_extractions_tokens_non_negative"),
        CheckConstraint("jsonb_typeof(warnings) = 'array'", name="ck_guideline_extractions_warnings_array"),
        Index("ix_guideline_extractions_user_created", "user_id", text("created_at DESC")),
        Index("ix_guideline_extractions_user_status", "user_id", "status"),
        Index("ix_guideline_extractions_user_hash", "user_id", "source_text_hash"),
    )

