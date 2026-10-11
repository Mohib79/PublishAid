from __future__ import annotations
from typing import TYPE_CHECKING, Any
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
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
    from app.db.models.journal import Journal
    from app.db.models.template import Template
    from app.db.models.conversion_job import ConversionJob
    from app.db.models.compliance_report import ComplianceReport

class GuidelineRule(Base):
    __tablename__ = "guideline_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    journal: Mapped[Journal | None] = relationship("Journal", back_populates="guideline_rules")
    templates: Mapped[list[Template]] = relationship("Template", back_populates="rule")
    conversion_jobs: Mapped[list[ConversionJob]] = relationship(
        "ConversionJob",
        back_populates="guideline_rule",
    )
    compliance_reports: Mapped[list[ComplianceReport]] = relationship(
        "ComplianceReport",
        back_populates="rule",
    )

    __table_args__ = (
        CheckConstraint("jsonb_typeof(rules) = 'object'", name="ck_guideline_rules_object"),
        Index("ix_guideline_rules_journal_active", "journal_id", "is_active"),
    )
