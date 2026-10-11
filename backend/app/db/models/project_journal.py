from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.journal import Journal

class ProjectJournal(Base):
    __tablename__ = "project_journals"

    project_journal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    journal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="RESTRICT"),
        nullable=False,
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship("Project", back_populates="project_journals")
    journal: Mapped[Journal] = relationship("Journal", back_populates="project_matches")

    __table_args__ = (
        UniqueConstraint("project_id", "journal_id", name="uq_project_journals_project_journal"),
        Index(
            "uq_project_journals_single_selected",
            "project_id",
            unique=True,
            postgresql_where=text("is_selected = true"),
        ),
    )
