from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    String,
    Integer,
    Float,
    Text,
    DateTime,
    Enum,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.guideline_rule import GuidelineRule
    from app.db.models.template import Template
    from app.db.models.project_journal import ProjectJournal

class Journal(Base):
    __tablename__ = "journals"

    journal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_title: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    issn: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    subject_category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    citescore: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    quartile: Mapped[str | None] = mapped_column(
        Enum("Q1", "Q2", "Q3", "Q4", native_enum=False, create_constraint=True, name="ck_journals_quartile"),
        nullable=True,
    )
    aims_and_scope: Mapped[str] = mapped_column(Text, nullable=False)
    open_access_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding = mapped_column(Vector(768), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    guideline_rules: Mapped[list[GuidelineRule]] = relationship(
        "GuidelineRule",
        back_populates="journal",
        passive_deletes=True,
    )
    templates: Mapped[list[Template]] = relationship(
        "Template",
        back_populates="journal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    project_matches: Mapped[list[ProjectJournal]] = relationship(
        "ProjectJournal",
        back_populates="journal",
        passive_deletes=True,
    )


    __table_args__ = (
        CheckConstraint("review_weeks >= 0", name="ck_journals_review_weeks_non_negative"),
        CheckConstraint(
            "acceptance_rate >= 0 AND acceptance_rate <= 100",
            name="ck_journals_acceptance_rate_range",
        ),
        Index(
            "ix_journals_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
