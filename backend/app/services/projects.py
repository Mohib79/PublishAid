import re
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.project import Project
from app.db.models.user import User

ALLOWED_STATUSES = {"draft", "in_progress", "ready_to_submit", "submitted"}


def normalize_title(title: str) -> str:
    """Trim, collapse whitespace runs, check length 1..300, reject control characters and NUL."""
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title is required and cannot be empty",
        )
    if "\x00" in title or re.search(r"[\x01-\x1f\x7f]", title):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title contains invalid control characters",
        )
    # Collapse multiple whitespace characters into a single space
    cleaned = " ".join(title.strip().split())
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title cannot be empty or whitespace only",
        )
    if len(cleaned) > 300:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title cannot exceed 300 characters",
        )
    return cleaned


def normalize_research_field(field_val: str | None) -> str | None:
    if field_val is None:
        return None
    cleaned = field_val.strip()
    if not cleaned:
        return None
    if len(cleaned) > 150:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Research field cannot exceed 150 characters",
        )
    return cleaned


def normalize_abstract(abstract_val: str | None) -> str | None:
    if abstract_val is None:
        return None
    cleaned = abstract_val.strip()
    if not cleaned:
        return None
    if len(cleaned) > 10000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Abstract cannot exceed 10,000 characters",
        )
    return cleaned


def normalize_keywords(keywords_val: Any) -> list[str]:
    if not keywords_val:
        return []
    items: list[str] = []
    if isinstance(keywords_val, str):
        items = keywords_val.split(",")
    elif isinstance(keywords_val, list):
        items = [str(x) for x in keywords_val]

    seen = set()
    result = []
    for item in items:
        cleaned = item.strip()
        if not cleaned:
            continue
        if len(cleaned) > 60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Keyword '{cleaned}' exceeds maximum length of 60 characters",
            )
        lower_key = cleaned.lower()
        if lower_key not in seen:
            seen.add(lower_key)
            result.append(cleaned)

    if len(result) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 20 keywords allowed",
        )
    return result


def normalize_status(status_val: str | None) -> str:
    if not status_val or status_val not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}",
        )
    return status_val


def get_owned_project_or_404(db: Session, user: User, project_id: int) -> Project:
    """Always returns 404 for unknown or foreign projects to prevent ID enumeration."""
    project = db.execute(
        select(Project).where(
            Project.project_id == project_id,
            Project.user_id == user.user_id,
        )
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def check_project_limit(db: Session, user_id: int) -> None:
    """Check race-safe cap by locking the user row."""
    # Lock the user row to serialize parallel project creation for this user
    user = db.execute(
        select(User).where(User.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    count = db.execute(
        select(func.count(Project.project_id)).where(Project.user_id == user_id)
    ).scalar() or 0

    if count >= settings.MAX_PROJECTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project limit reached",
        )

