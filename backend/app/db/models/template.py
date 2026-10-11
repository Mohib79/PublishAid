from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.journal import Journal
    from app.db.models.guideline_rule import GuidelineRule

class Template(Base):
    __tablename__ = "templates"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("journals.journal_id", ondelete="CASCADE"),
        nullable=True,
    )
    rule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("guideline_rules.rule_id", ondelete="SET NULL"),
        nullable=True,
    )
    template_format: Mapped[str] = mapped_column(
        Enum("latex", "word", native_enum=False, create_constraint=True, name="ck_templates_format"),
        nullable=False,
    )
    template_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    journal: Mapped[Journal | None] = relationship("Journal", back_populates="templates")
    rule: Mapped[GuidelineRule | None] = relationship("GuidelineRule", back_populates="templates")
