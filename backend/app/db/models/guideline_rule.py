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
    from app.db.models.user import User
    from app.db.models.journal import Journal
    from app.db.models.template import Template
    from app.db.models.conversion_job import ConversionJob
    from app.db.models.compliance_report import ComplianceReport
    from app.db.models.guideline_extraction import GuidelineExtraction
    from app.db.models.project import Project

class GuidelineRule(Base):
    __tablename__ = "guideline_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
    )
    journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="Default Rules",
        server_default="Default Rules",
    )
    origin: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="seed",
        server_default="seed",
    )
    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
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
    lineage_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_rules.rule_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_from_extraction_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_extractions.extraction_id", ondelete="SET NULL"),
        nullable=True,
    )
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

    owner: Mapped[User | None] = relationship("User", back_populates="guideline_rules")
    journal: Mapped[Journal | None] = relationship("Journal", back_populates="guideline_rules")
    lineage_root: Mapped[GuidelineRule | None] = relationship("GuidelineRule", remote_side=[rule_id], foreign_keys=[lineage_id])
    extraction: Mapped[GuidelineExtraction | None] = relationship("GuidelineExtraction", foreign_keys=[created_from_extraction_id])
    templates: Mapped[list[Template]] = relationship("Template", back_populates="rule")
    conversion_jobs: Mapped[list[ConversionJob]] = relationship(
        "ConversionJob",
        back_populates="guideline_rule",
    )
    compliance_reports: Mapped[list[ComplianceReport]] = relationship(
        "ComplianceReport",
        back_populates="rule",
    )
    projects: Mapped[list[Project]] = relationship("Project", back_populates="guideline_rule")

    __table_args__ = (
        CheckConstraint("jsonb_typeof(rules) = 'object'", name="ck_guideline_rules_object"),
        CheckConstraint("jsonb_typeof(provenance) = 'object'", name="ck_guideline_rules_provenance_object"),
        CheckConstraint("origin IN ('extracted', 'manual', 'seed')", name="ck_guideline_rules_origin"),
        Index("ix_guideline_rules_journal_active", "journal_id", "is_active"),
        Index("ix_guideline_rules_owner_journal_active", "owner_user_id", "journal_id", "is_active"),
    )
