from __future__ import annotations
from typing import TYPE_CHECKING, Any
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
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

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    project_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", backref="activity_logs")
    project: Mapped[Project | None] = relationship("Project", backref="activity_logs")

    __table_args__ = (
        Index("ix_activity_logs_user_created", "user_id", text("created_at DESC")),
        Index("ix_activity_logs_project_created", "project_id", text("created_at DESC")),
    )

