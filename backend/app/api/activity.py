from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.activity_log import ActivityLog
from app.db.models.journal import Journal
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.project import ActivityItemOut

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/recent", response_model=list[ActivityItemOut])
def get_recent_activity(
    limit: int = Query(20, ge=1, le=50),
    before: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityItemOut]:
    query = (
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.user_id)
        .order_by(desc(ActivityLog.created_at), desc(ActivityLog.log_id))
    )
    if before:
        query = query.where(ActivityLog.log_id < before)

    logs = db.execute(query.limit(limit)).scalars().all()

    # Batch resolve journal titles
    journal_ids = set()
    for log in logs:
        jid = log.details.get("journalId")
        if jid:
            journal_ids.add(jid)

    journal_map = {}
    if journal_ids:
        j_rows = db.execute(
            select(Journal.journal_id, Journal.journal_title).where(Journal.journal_id.in_(journal_ids))
        ).all()
        journal_map = {row[0]: row[1] for row in j_rows}

    return [
        ActivityItemOut(
            id=str(log.log_id),
            project_id=str(log.project_id) if log.project_id else None,
            project_title=log.project_title,
            event_type=log.event_type,
            details=log.details,
            journal_title=journal_map.get(log.details.get("journalId")),
            created_at=log.created_at,
        )
        for log in logs
    ]

