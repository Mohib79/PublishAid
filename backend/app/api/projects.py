import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.user import User
from app.db.models.activity_log import ActivityLog
from app.db.session import get_db
from app.schemas.journal import JournalItemOut, MatchJournalItemOut
from app.schemas.project import (
    ProjectCreate,
    ProjectPatch,
    ProjectItemOut,
    ProjectListItemOut,
    ProjectListResponse,
    ProjectOverviewOut,
    ProjectGuidelineRuleSetInfo,
    TargetJournalInfo,
    ProjectCounts,
    ManuscriptInfo,
    ActivityItemOut,
    ShortlistBody,
)
from app.services.activity import log_activity
from app.services.guidelines.ruleset_service import resolve_effective_rule_for_project
from app.services.projects import (
    get_owned_project_or_404,
    check_project_limit,
    normalize_title,
    normalize_research_field,
    normalize_abstract,
    normalize_keywords,
    normalize_status,
)
from app.services.storage import StorageService

router = APIRouter(prefix="/projects", tags=["projects"])


def build_manuscript_info(project: Project, db: Session) -> Optional[ManuscriptInfo]:
    """Helper to check manuscript availability on disk and heal DB if missing."""
    if not project.current_file_path and not project.file_deleted_at and not project.manuscript_filename:
        return None

    if not project.manuscript_uploaded_at or not project.manuscript_filename:
        return None

    ttl_delta = timedelta(minutes=settings.WORKSPACE_FILE_TTL_MINUTES)
    expires_at = project.manuscript_uploaded_at + ttl_delta

    available = False
    if project.current_file_path and not project.file_deleted_at:
        full_path = Path(settings.STORAGE_ROOT) / project.current_file_path
        if full_path.is_file():
            available = True
        else:
            # Self-heal row: missing on disk
            project.file_deleted_at = datetime.now(timezone.utc)
            project.current_file_path = None
            db.commit()

    return ManuscriptInfo(
        file_name=project.manuscript_filename,
        size_bytes=project.manuscript_size_bytes or 0,
        uploaded_at=project.manuscript_uploaded_at,
        available=available,
        expires_at=expires_at,
    )


def project_to_item_out(project: Project, db: Session) -> ProjectItemOut:
    return ProjectItemOut(
        id=str(project.project_id),
        title=project.project_title,
        research_field=project.research_field,
        field=project.research_field or "",
        abstract=project.manuscript_abstract,
        keywords=project.keywords or [],
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        manuscript=build_manuscript_info(project, db),
    )


# --- 5.1 Endpoints ---

@router.post("", response_model=ProjectItemOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectItemOut:
    # 1. Check cap race-safely
    check_project_limit(db, current_user.user_id)

    # 2. Normalize inputs
    clean_title = normalize_title(data.title)
    clean_field = normalize_research_field(data.research_field)
    clean_abstract = normalize_abstract(data.abstract)
    clean_keywords = normalize_keywords(data.keywords)

    # 3. Create project (always status 'draft')
    project = Project(
        user_id=current_user.user_id,
        project_title=clean_title,
        research_field=clean_field,
        manuscript_abstract=clean_abstract,
        keywords=clean_keywords,
        status="draft",
    )
    db.add(project)
    db.flush()

    # 4. Log activity inside caller's transaction
    log_activity(db, current_user.user_id, project, "project_created")

    db.commit()
    db.refresh(project)
    return project_to_item_out(project, db)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    sort: str = Query("updatedAt"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectListResponse:
    # Validate sort and order
    sort_column_map = {
        "updatedAt": Project.updated_at,
        "createdAt": Project.created_at,
        "title": Project.project_title,
    }
    if sort not in sort_column_map:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort field: {sort}. Allowed: {', '.join(sort_column_map.keys())}",
        )
    if order.lower() not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order must be 'asc' or 'desc'",
        )

    base_query = select(Project).where(Project.user_id == current_user.user_id)

    # Status filter
    if status_filter and status_filter.strip():
        st_clean = status_filter.strip().lower()
        if st_clean not in {"draft", "in_progress", "ready_to_submit", "submitted"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid status filter",
            )
        base_query = base_query.where(Project.status == st_clean)

    # Search filter (literal match for %, _, \)
    if search and search.strip():
        term = search.strip()
        escaped_term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_term}%"
        base_query = base_query.where(
            or_(
                Project.project_title.ilike(pattern, escape="\\"),
                Project.research_field.ilike(pattern, escape="\\"),
            )
        )

    # Count total
    total = db.execute(
        select(func.count()).select_from(base_query.subquery())
    ).scalar() or 0

    # Sorting with stable tie-break on project_id
    col = sort_column_map[sort]
    if order.lower() == "desc":
        base_query = base_query.order_by(desc(col), desc(Project.project_id))
    else:
        base_query = base_query.order_by(asc(col), asc(Project.project_id))

    offset = (page - 1) * page_size
    projects = db.execute(base_query.offset(offset).limit(page_size)).scalars().all()

    if not projects:
        return ProjectListResponse(items=[], total=total, page=page, page_size=page_size)

    proj_ids = [p.project_id for p in projects]

    # Batch query shortlisted count (avoid N+1)
    shortlist_counts = dict(
        db.execute(
            select(ProjectJournal.project_id, func.count(ProjectJournal.journal_id))
            .where(
                ProjectJournal.project_id.in_(proj_ids),
                ProjectJournal.is_shortlisted.is_(True),
            )
            .group_by(ProjectJournal.project_id)
        ).all()
    )

    # Batch query target journals
    target_journals = dict(
        db.execute(
            select(ProjectJournal.project_id, Journal.journal_title)
            .join(Journal, ProjectJournal.journal_id == Journal.journal_id)
            .where(
                ProjectJournal.project_id.in_(proj_ids),
                ProjectJournal.is_selected.is_(True),
            )
        ).all()
    )

    items: list[ProjectListItemOut] = []
    for p in projects:
        has_file = bool(p.current_file_path and not p.file_deleted_at)
        items.append(
            ProjectListItemOut(
                id=str(p.project_id),
                title=p.project_title,
                research_field=p.research_field,
                field=p.research_field or "",
                status=p.status,
                created_at=p.created_at,
                updated_at=p.updated_at,
                shortlisted_count=shortlist_counts.get(p.project_id, 0),
                has_manuscript=has_file,
                target_journal_title=target_journals.get(p.project_id),
            )
        )

    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{project_id}", response_model=ProjectOverviewOut)
def get_project_overview(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOverviewOut:
    project = get_owned_project_or_404(db, current_user, project_id)

    # Target journal
    selected_pj = db.execute(
        select(Journal)
        .join(ProjectJournal, ProjectJournal.journal_id == Journal.journal_id)
        .where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_selected.is_(True),
        )
    ).scalar_one_or_none()

    target_info = (
        TargetJournalInfo(
            id=str(selected_pj.journal_id),
            title=selected_pj.journal_title,
            publisher=selected_pj.publisher,
        )
        if selected_pj
        else None
    )

    # Shortlisted count
    sl_count = db.execute(
        select(func.count(ProjectJournal.journal_id)).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_shortlisted.is_(True),
        )
    ).scalar() or 0

    # Recent activity (up to 5)
    recent_logs = db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.project_id == project.project_id,
            ActivityLog.user_id == current_user.user_id,
        )
        .order_by(desc(ActivityLog.created_at))
        .limit(5)
    ).scalars().all()

    activity_items = [
        ActivityItemOut(
            id=str(log.log_id),
            project_id=str(log.project_id) if log.project_id else None,
            project_title=log.project_title,
            event_type=log.event_type,
            details=log.details,
            created_at=log.created_at,
        )
        for log in recent_logs
    ]

    # Effective guideline rule set
    eff_rule, eff_source = resolve_effective_rule_for_project(db, project)
    rule_set_info = (
        ProjectGuidelineRuleSetInfo(
            id=str(eff_rule.rule_id),
            name=eff_rule.name,
            version=eff_rule.version,
            source=eff_source or "project",
        )
        if eff_rule
        else None
    )

    return ProjectOverviewOut(
        id=str(project.project_id),
        title=project.project_title,
        research_field=project.research_field,
        field=project.research_field or "",
        abstract=project.manuscript_abstract,
        keywords=project.keywords or [],
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        manuscript=build_manuscript_info(project, db),
        shortlisted_count=sl_count,
        target_journal=target_info,
        guideline_rule_set=rule_set_info,
        counts=ProjectCounts(conversions=0, compliance_reports=0),
        recent_activity=activity_items,
    )


@router.patch("/{project_id}", response_model=ProjectItemOut)
def patch_project(
    project_id: int,
    data: ProjectPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectItemOut:
    fields_set = data.model_dump(exclude_unset=True)
    if not fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty patch body. Provide at least one field to update.",
        )

    project = get_owned_project_or_404(db, current_user, project_id)

    changed_fields = []
    status_changed = None

    if "title" in fields_set:
        new_title = normalize_title(data.title or "")
        if new_title != project.project_title:
            project.project_title = new_title
            changed_fields.append("title")

    if "research_field" in fields_set:
        new_field = normalize_research_field(data.research_field)
        if new_field != project.research_field:
            project.research_field = new_field
            changed_fields.append("researchField")

    if "abstract" in fields_set:
        new_abstract = normalize_abstract(data.abstract)
        if new_abstract != project.manuscript_abstract:
            project.manuscript_abstract = new_abstract
            changed_fields.append("abstract")

    if "keywords" in fields_set:
        new_kw = normalize_keywords(data.keywords)
        if new_kw != project.keywords:
            project.keywords = new_kw
            changed_fields.append("keywords")

    if "status" in fields_set:
        new_status = normalize_status(data.status)
        if new_status != project.status:
            status_changed = {"from": project.status, "to": new_status}
            project.status = new_status
            changed_fields.append("status")

    if not changed_fields:
        # Nothing actually changed
        return project_to_item_out(project, db)

    # Bump updated_at
    project.updated_at = datetime.now(timezone.utc)

    # Log activities
    if status_changed:
        log_activity(db, current_user.user_id, project, "project_status_changed", status_changed)
    if any(f != "status" for f in changed_fields):
        non_status_fields = [f for f in changed_fields if f != "status"]
        log_activity(db, current_user.user_id, project, "project_updated", {"fields": non_status_fields})

    db.commit()
    db.refresh(project)
    return project_to_item_out(project, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_owned_project_or_404(db, current_user, project_id)

    # Snapshot for deleted log
    log_activity(db, current_user.user_id, project, "project_deleted")

    # Storage cleanup best effort
    storage_folder = Path(settings.STORAGE_ROOT) / str(project.project_id)

    db.delete(project)
    db.commit()

    if storage_folder.is_dir():
        try:
            import shutil
            shutil.rmtree(storage_folder, ignore_errors=True)
        except Exception:
            pass


# --- Shortlist & Target Journal Endpoints ---

@router.put("/{project_id}/shortlist/{journal_id}", response_model=MatchJournalItemOut)
def shortlist_journal(
    project_id: int,
    journal_id: int,
    body: Optional[ShortlistBody] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchJournalItemOut:
    project = get_owned_project_or_404(db, current_user, project_id)
    journal = db.execute(
        select(Journal).where(Journal.journal_id == journal_id)
    ).scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal not found")

    pj = db.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.journal_id == journal.journal_id,
        )
    ).scalar_one_or_none()

    sim_score = body.similarity_score if body and body.similarity_score is not None else None

    if pj:
        pj.is_shortlisted = True
        if sim_score is not None:
            pj.similarity_score = sim_score
    else:
        pj = ProjectJournal(
            project_id=project.project_id,
            journal_id=journal.journal_id,
            similarity_score=sim_score,
            is_shortlisted=True,
            is_selected=False,
        )
        db.add(pj)

    project.updated_at = datetime.now(timezone.utc)
    log_activity(db, current_user.user_id, project, "journal_shortlisted", {"journalId": journal.journal_id})
    db.commit()

    item_dict = JournalItemOut.model_validate(journal).model_dump(by_alias=True)
    raw_sim = pj.similarity_score if pj.similarity_score is not None else 0.0
    match_score = int(round(raw_sim * 100)) if raw_sim else 0

    item_dict.update({
        "matchScore": match_score,
        "rawSimilarity": round(raw_sim, 4),
        "matchTag": None,
        "isShortlisted": True,
    })
    return MatchJournalItemOut.model_validate(item_dict)


@router.delete("/{project_id}/shortlist/{journal_id}")
def unshortlist_journal(
    project_id: int,
    journal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    project = get_owned_project_or_404(db, current_user, project_id)
    journal = db.execute(
        select(Journal).where(Journal.journal_id == journal_id)
    ).scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal not found")

    pj = db.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.journal_id == journal.journal_id,
        )
    ).scalar_one_or_none()

    if pj:
        was_selected = pj.is_selected
        # If target journal was selected, clearing shortlist also clears target to avoid constraint violation
        if was_selected:
            log_activity(db, current_user.user_id, project, "target_journal_cleared", {"journalId": journal.journal_id})
        db.delete(pj)
        project.updated_at = datetime.now(timezone.utc)
        log_activity(db, current_user.user_id, project, "journal_unshortlisted", {"journalId": journal.journal_id})
        db.commit()

    return {
        "success": True,
        "projectId": str(project.project_id),
        "journalId": str(journal.journal_id),
        "isShortlisted": False,
    }


@router.get("/{project_id}/shortlist", response_model=list[MatchJournalItemOut])
def get_project_shortlist(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MatchJournalItemOut]:
    project = get_owned_project_or_404(db, current_user, project_id)

    rows = db.execute(
        select(ProjectJournal, Journal)
        .join(Journal, ProjectJournal.journal_id == Journal.journal_id)
        .where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_shortlisted.is_(True),
        )
        .order_by(ProjectJournal.added_at.desc())
    ).all()

    results: list[MatchJournalItemOut] = []
    for pj, j in rows:
        item_dict = JournalItemOut.model_validate(j).model_dump(by_alias=True)
        raw_sim = pj.similarity_score if pj.similarity_score is not None else 0.0
        match_score = int(round(raw_sim * 100)) if raw_sim else 0

        item_dict.update({
            "matchScore": match_score,
            "rawSimilarity": round(raw_sim, 4),
            "matchTag": None,
            "isShortlisted": True,
        })
        results.append(MatchJournalItemOut.model_validate(item_dict))

    return results


@router.get("/{project_id}/activity", response_model=list[ActivityItemOut])
def get_project_activity(
    project_id: int,
    limit: int = Query(20, ge=1, le=50),
    before: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityItemOut]:
    project = get_owned_project_or_404(db, current_user, project_id)

    query = (
        select(ActivityLog)
        .where(
            ActivityLog.project_id == project.project_id,
            ActivityLog.user_id == current_user.user_id,
        )
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


# --- Part B: Target Journal Endpoints (Phase W9) ---

@router.put("/{project_id}/target-journal/{journal_id}", response_model=ProjectOverviewOut)
def set_target_journal(
    project_id: int,
    journal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOverviewOut:
    # Lock project row first to serialize concurrent requests
    project = db.execute(
        select(Project).where(
            Project.project_id == project_id,
            Project.user_id == current_user.user_id,
        ).with_for_update()
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    journal = db.execute(
        select(Journal).where(Journal.journal_id == journal_id)
    ).scalar_one_or_none()
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal not found")

    # Clear is_selected on all other journals for this project
    all_pjs = db.execute(
        select(ProjectJournal).where(ProjectJournal.project_id == project.project_id)
    ).scalars().all()

    target_pj = None
    for pj in all_pjs:
        if pj.journal_id == journal.journal_id:
            target_pj = pj
        elif pj.is_selected:
            pj.is_selected = False

    if target_pj:
        target_pj.is_selected = True
        target_pj.is_shortlisted = True
    else:
        target_pj = ProjectJournal(
            project_id=project.project_id,
            journal_id=journal.journal_id,
            is_selected=True,
            is_shortlisted=True,
        )
        db.add(target_pj)

    project.updated_at = datetime.now(timezone.utc)
    log_activity(db, current_user.user_id, project, "target_journal_set", {"journalId": journal.journal_id})
    db.commit()

    return get_project_overview(project_id, db, current_user)


@router.delete("/{project_id}/target-journal", response_model=ProjectOverviewOut)
def clear_target_journal(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOverviewOut:
    project = get_owned_project_or_404(db, current_user, project_id)

    selected_pj = db.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_selected.is_(True),
        )
    ).scalar_one_or_none()

    if selected_pj:
        selected_pj.is_selected = False  # Stays shortlisted
        project.updated_at = datetime.now(timezone.utc)
        log_activity(db, current_user.user_id, project, "target_journal_cleared", {"journalId": selected_pj.journal_id})
        db.commit()

    return get_project_overview(project_id, db, current_user)


# --- Part B: Manuscript Attachment & Storage (Phase W10) ---

@router.post("/{project_id}/manuscript", response_model=ManuscriptInfo, status_code=status.HTTP_201_CREATED)
async def upload_manuscript(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ManuscriptInfo:
    project = get_owned_project_or_404(db, current_user, project_id)

    storage = StorageService(settings.STORAGE_ROOT)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    # Stream upload with size check and content sniffing
    rel_key, display_name, size_bytes = await storage.save_manuscript_stream(
        project_id=project.project_id,
        upload_file=file,
        max_bytes=max_bytes,
    )

    old_file_key = project.current_file_path
    was_replaced = bool(old_file_key and not project.file_deleted_at)

    try:
        now = datetime.now(timezone.utc)
        project.current_file_path = rel_key
        project.manuscript_filename = display_name
        project.manuscript_size_bytes = size_bytes
        project.manuscript_uploaded_at = now
        project.file_deleted_at = None
        project.updated_at = now

        ext_clean = Path(display_name).suffix.lower().lstrip(".")
        log_activity(
            db,
            current_user.user_id,
            project,
            "manuscript_uploaded",
            {"extension": ext_clean, "sizeBytes": size_bytes, "replaced": was_replaced},
        )
        db.commit()

        # Safely delete old file on successful DB update
        if was_replaced and old_file_key and old_file_key != rel_key:
            storage.delete_manuscript_file(old_file_key)

    except Exception:
        db.rollback()
        # Clean up newly written file on DB error
        storage.delete_manuscript_file(rel_key)
        raise

    db.refresh(project)
    info = build_manuscript_info(project, db)
    if not info:
        raise HTTPException(status_code=500, detail="Failed to construct manuscript info")
    return info


@router.delete("/{project_id}/manuscript", status_code=status.HTTP_204_NO_CONTENT)
def delete_manuscript(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_owned_project_or_404(db, current_user, project_id)

    if not project.current_file_path and not project.manuscript_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manuscript attached",
        )

    storage = StorageService(settings.STORAGE_ROOT)
    storage.delete_manuscript_file(project.current_file_path)

    now = datetime.now(timezone.utc)
    project.current_file_path = None
    project.manuscript_filename = None
    project.manuscript_size_bytes = None
    project.file_deleted_at = now
    project.updated_at = now

    log_activity(db, current_user.user_id, project, "manuscript_removed")
    db.commit()
