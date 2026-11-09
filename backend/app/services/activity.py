from typing import Any
from sqlalchemy.orm import Session
from app.db.models.activity_log import ActivityLog
from app.db.models.project import Project

# Whitelist of allowed detail keys per event type (Privacy rule: Section 4.3 & Phase W3)
ALLOWED_EVENT_DETAILS: dict[str, set[str]] = {
    "project_created": set(),
    "project_updated": {"fields"},
    "project_status_changed": {"from", "to"},
    "project_deleted": set(),
    "manuscript_uploaded": {"extension", "sizeBytes", "replaced"},
    "manuscript_removed": set(),
    "manuscript_purged": set(),
    "journal_shortlisted": {"journalId"},
    "journal_unshortlisted": {"journalId"},
    "target_journal_set": {"journalId"},
    "target_journal_cleared": set(),
}

def log_activity(
    db: Session,
    user_id: int,
    project: Project | None,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> ActivityLog:
    """
    Logs an activity inside the caller's transaction.
    Enforces the event type check, field whitelist for privacy, and captures the title snapshot.
    """
    if event_type not in ALLOWED_EVENT_DETAILS:
        raise ValueError(f"Unknown event type: {event_type}")

    allowed_keys = ALLOWED_EVENT_DETAILS[event_type]
    raw_details = details or {}
    filtered_details = {k: v for k, v in raw_details.items() if k in allowed_keys}

    project_id = project.project_id if project else None
    project_title = project.project_title if project else None

    log_entry = ActivityLog(
        user_id=user_id,
        project_id=project_id,
        project_title=project_title,
        event_type=event_type,
        details=filtered_details,
    )
    db.add(log_entry)
    return log_entry
