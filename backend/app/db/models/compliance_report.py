from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.journal import Journal
    from app.db.models.guideline_rule import GuidelineRule
    from app.db.models.compliance_issue import ComplianceIssue

class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_rules.rule_id", ondelete="SET NULL"),
        nullable=True,
    )
    overall_status: Mapped[str] = mapped_column(
        Enum("passed", "failed", native_enum=False, create_constraint=True, name="ck_compliance_reports_status"),
        nullable=False,
    )
    passed_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    failed_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    report_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship("Project", back_populates="compliance_reports")
    journal: Mapped[Journal | None] = relationship("Journal")
    rule: Mapped[GuidelineRule | None] = relationship("GuidelineRule", back_populates="compliance_reports")
    issues: Mapped[list[ComplianceIssue]] = relationship(
        "ComplianceIssue",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("passed_checks >= 0", name="ck_compliance_reports_passed_checks_non_negative"),
        CheckConstraint("failed_checks >= 0", name="ck_compliance_reports_failed_checks_non_negative"),
    )
