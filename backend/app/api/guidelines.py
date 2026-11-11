"""
Guideline Extraction & Rule Set Endpoints.
Reference: Guideline Extraction Plan Section 6.1, 10.12, 10.13, 10.14.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Literal
from urllib.parse import urlparse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, desc, or_, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.guideline_rule import GuidelineRule
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db, SessionLocal
from app.schemas.guideline import (
    CreateExtractionRequest,
    ConfirmExtractionRequest,
    RuleSetCreateRequest,
    RuleSetPatchRequest,
    RuleSetOut,
    RuleSetListOut,
    JournalEffectiveRulesOut,
    ExtractionJobOut,
    ExtractionListOut,
    ExtractionWarning,
    ExtractionError,
    SourceMetadata,
)
from app.services.activity import log_activity
from app.services.guidelines.fetcher import normalize_and_validate_url, FetchError
from app.services.guidelines.ruleset_service import (
    validate_rules_payload,
    check_unreviewed_low_confidence_fields,
    build_ruleset_provenance,
    resolve_effective_rule_for_journal,
    resolve_effective_rule_for_project,
    RuleValidationError,
)
from app.services.guidelines.runner import (
    check_and_enforce_quotas,
    find_in_flight_duplicate,
    run_extraction_job,
    QuotaError,
)
from app.services.guidelines.schema import get_schema_metadata

router = APIRouter(prefix="/guidelines", tags=["guidelines"])
journals_guidelines_router = APIRouter(prefix="/journals", tags=["guidelines"])
projects_guidelines_router = APIRouter(prefix="/projects", tags=["guidelines"])


def build_job_response(job: GuidelineExtraction) -> ExtractionJobOut:
    """Builds a standardized camelCase ExtractionJobOut response model."""
    source_meta = None
    if job.source_text:
        words = len(job.source_text.split())
        source_meta = SourceMetadata(
            title=None,
            word_count=words,
            language="en",
            truncated=any(w.get("code") == "TRUNCATED" for w in (job.warnings or [])),
        )

    warning_models = [
        ExtractionWarning(
            code=w.get("code", "WARNING"),
            message=w.get("message", ""),
            path=w.get("path"),
        )
        for w in (job.warnings or [])
    ]

    error_model = None
    if job.error_code:
        error_model = ExtractionError(
            code=job.error_code,
            message=job.error_message or "Extraction failed",
        )

    return ExtractionJobOut(
        id=str(job.extraction_id),
        status=job.status,
        step=job.step,
        cached=job.cached,
        source_type=job.source_type,
        source_url=job.source_url,
        final_url=job.final_url,
        journal_id=str(job.journal_id) if job.journal_id else None,
        project_id=str(job.project_id) if job.project_id else None,
        source=source_meta,
        warnings=warning_models,
        draft=job.draft,
        error=error_model,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def build_ruleset_response(rule: GuidelineRule) -> RuleSetOut:
    """Builds a standardized camelCase RuleSetOut response model."""
    journal_title = rule.journal.journal_title if rule.journal else None
    root_id = str(rule.lineage_id or rule.rule_id)
    return RuleSetOut(
        id=str(rule.rule_id),
        name=rule.name,
        journal_id=str(rule.journal_id) if rule.journal_id else None,
        journal_title=journal_title,
        origin=rule.origin,
        version=rule.version,
        is_active=rule.is_active,
        is_system=(rule.owner_user_id is None),
        schema_version=rule.schema_version,
        rules=rule.rules or {},
        provenance=rule.provenance or {},
        source_url=rule.source_url,
        lineage_id=root_id,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


# ===========================================================================
# Schema Metadata
# ===========================================================================

@router.get("/schema")
def get_guidelines_schema():
    """Returns the JSON schema metadata, allowed enums, canonical sections, and numerical ranges."""
    return get_schema_metadata()


# ===========================================================================
# Extraction Jobs
# ===========================================================================

@router.post("/extractions", status_code=status.HTTP_202_ACCEPTED, response_model=ExtractionJobOut)
async def create_extraction(
    data: CreateExtractionRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submits a guideline extraction job (URL or pasted text).
    Returns 202 with the queued job, or 200 if an identical job is currently in-flight.
    """
    # 1. Foreign key validations
    journal_id_int = None
    if data.journal_id is not None:
        try:
            journal_id_int = int(data.journal_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Journal not found")
        journal = db.get(Journal, journal_id_int)
        if not journal:
            raise HTTPException(status_code=404, detail="Journal not found")

    project_id_int = None
    if data.project_id is not None:
        try:
            project_id_int = int(data.project_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Project not found")
        project = db.get(Project, project_id_int)
        if not project or project.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Project not found")

    # 2. Check quotas
    try:
        check_and_enforce_quotas(db, current_user.user_id)
    except QuotaError as qe:
        headers = {}
        if qe.retry_after:
            headers["Retry-After"] = str(qe.retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=qe.message,
            headers=headers,
        )

    # 3. Normalize input & calculate hash
    normalized_url = None
    text_hash = None
    if data.source_type == "url":
        try:
            normalized_url, _, _ = normalize_and_validate_url(data.url)
        except FetchError as fe:
            raise HTTPException(status_code=422, detail=fe.message)
    else:
        text_hash = hashlib.sha256(data.text.encode("utf-8")).hexdigest()

    # 4. Check in-flight duplicate (GE-JOB-12)
    in_flight = find_in_flight_duplicate(db, current_user.user_id, data.source_type, normalized_url, text_hash)
    if in_flight:
        response.status_code = status.HTTP_200_OK
        return build_job_response(in_flight)

    # 5. Create new GuidelineExtraction row
    job = GuidelineExtraction(
        user_id=current_user.user_id,
        project_id=project_id_int,
        journal_id=journal_id_int,
        source_type=data.source_type,
        source_url=normalized_url,
        source_text=data.text if data.source_type == "text" else None,
        source_text_hash=text_hash,
        status="queued",
        step="queued",
        warnings=[],
        schema_version=1,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 6. Kick off background task via FastAPI BackgroundTasks
    background_tasks.add_task(run_extraction_job, job.extraction_id, SessionLocal)

    return build_job_response(job)


@router.get("/extractions", response_model=ExtractionListOut)
def list_extractions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists current user's extractions (newest first, paginated)."""
    offset = (page - 1) * page_size
    q = (
        select(GuidelineExtraction)
        .where(GuidelineExtraction.user_id == current_user.user_id)
        .order_by(desc(GuidelineExtraction.created_at))
    )

    total = db.scalar(
        select(func.count(GuidelineExtraction.extraction_id)).where(
            GuidelineExtraction.user_id == current_user.user_id
        )
    ) or 0

    items = db.scalars(q.offset(offset).limit(page_size)).all()

    return ExtractionListOut(
        items=[build_job_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/extractions/{extraction_id}", response_model=ExtractionJobOut)
def get_extraction(
    extraction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gets extraction status and, when completed, the draft rules."""
    try:
        ext_id = int(extraction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    job = db.get(GuidelineExtraction, ext_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    # If job has been running or queued for longer than 3 minutes, automatically mark it as interrupted
    if job.status in ("queued", "running") and job.created_at:
        now = datetime.now(timezone.utc)
        created = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() > 180:
            job.status = "failed"
            job.step = "done"
            job.error_code = "INTERRUPTED"
            job.error_message = "Extraction timed out or was interrupted. Please try again."
            job.completed_at = now
            db.commit()
            db.refresh(job)

    return build_job_response(job)


@router.post("/extractions/{extraction_id}/cancel", response_model=ExtractionJobOut)
def cancel_extraction(
    extraction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels a queued or running extraction job."""
    try:
        ext_id = int(extraction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    job = db.get(GuidelineExtraction, ext_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job with status '{job.status}'",
        )

    job.status = "cancelled"
    job.step = "done"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    return build_job_response(job)


@router.post("/extractions/{extraction_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=ExtractionJobOut)
async def retry_extraction(
    extraction_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retries a failed extraction job."""
    try:
        ext_id = int(extraction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    job = db.get(GuidelineExtraction, ext_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only failed jobs can be retried (current status: '{job.status}')",
        )

    # Check quotas before retry
    try:
        check_and_enforce_quotas(db, current_user.user_id)
    except QuotaError as qe:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=qe.message)

    job.status = "queued"
    job.step = "queued"
    job.error_code = None
    job.error_message = None
    job.warnings = []
    job.completed_at = None
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_extraction_job, job.extraction_id, SessionLocal)

    return build_job_response(job)


@router.delete("/extractions/{extraction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extraction(
    extraction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes an extraction job / draft. If running, cancels it first."""
    try:
        ext_id = int(extraction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    job = db.get(GuidelineExtraction, ext_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    if job.status in ("queued", "running"):
        job.status = "cancelled"
        db.commit()

    db.delete(job)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# Rule Set Operations (Confirm, CRUD, Versioning, Activate, Copy)
# ===========================================================================

@router.post("/extractions/{extraction_id}/confirm", status_code=status.HTTP_201_CREATED, response_model=RuleSetOut)
def confirm_extraction(
    extraction_id: str,
    data: ConfirmExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirms an extraction draft into a saved, active GuidelineRule row.
    Reference: Section 7.6, 10.13 (GE-RS-01 to GE-RS-18).
    """
    try:
        ext_id = int(extraction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    job = db.get(GuidelineExtraction, ext_id)
    if not job or job.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Guideline extraction not found")

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot confirm job with status '{job.status}'. Only completed jobs can be confirmed.",
        )

    if job.confirmed_rule_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This extraction has already been confirmed.",
        )

    # 1. Validate Journal
    target_journal_id = None
    if data.journal_id is not None:
        try:
            target_journal_id = int(data.journal_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Journal not found")
        journal = db.get(Journal, target_journal_id)
        if not journal:
            raise HTTPException(status_code=404, detail="Journal not found")
    elif job.journal_id:
        target_journal_id = job.journal_id
        journal = db.get(Journal, target_journal_id)
    else:
        journal = None

    # 2. Validate Project
    target_project = None
    if data.project_id is not None:
        try:
            p_id = int(data.project_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Project not found")
        target_project = db.get(Project, p_id)
        if not target_project or target_project.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Project not found")
    elif job.project_id:
        target_project = db.get(Project, job.project_id)
        if target_project and target_project.user_id != current_user.user_id:
            target_project = None

    # 3. Validate rules payload
    try:
        validated_rules = validate_rules_payload(data.rules)
    except RuleValidationError as rve:
        if rve.code == "NO_RULES":
            raise HTTPException(status_code=422, detail={"code": "NO_RULES", "message": rve.message})
        raise HTTPException(status_code=422, detail=rve.errors or rve.message)

    # 4. Enforce review of low-confidence fields (GE-RS-03, GE-RS-04, GE-RS-05)
    unreviewed = check_unreviewed_low_confidence_fields(job.draft, validated_rules, data.acknowledged_fields)
    if unreviewed:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNREVIEWED_FIELDS",
                "message": "Low-confidence fields must be acknowledged or edited.",
                "unreviewedFields": unreviewed,
            },
        )

    # 5. Name validation and generation (GE-RS-19)
    if data.name is not None and data.name.strip():
        if len(data.name.strip()) > 200:
            raise HTTPException(status_code=422, detail="Name must not exceed 200 characters.")
        rule_name = data.name.strip()
    else:
        if journal:
            rule_name = f"{journal.journal_title} Author Guidelines"
        else:
            rule_name = f"Custom Guidelines {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        if len(rule_name) > 200:
            rule_name = rule_name[:200]

    # 6. Lineage and versioning (GE-RS-13, GE-RS-14)
    root_id = None
    next_ver = 1
    if target_journal_id:
        existing = db.scalars(
            select(GuidelineRule)
            .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == target_journal_id)
            .order_by(desc(GuidelineRule.version))
        ).all()
        if existing:
            root_id = existing[0].lineage_id or existing[0].rule_id
            next_ver = max(r.version for r in existing) + 1
            # Deactivate previous active version
            db.execute(
                update(GuidelineRule)
                .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == target_journal_id)
                .values(is_active=False)
            )

    # 7. Build provenance
    prov = build_ruleset_provenance(job.draft, validated_rules)

    # 8. Create GuidelineRule
    new_rule = GuidelineRule(
        owner_user_id=current_user.user_id,
        journal_id=target_journal_id,
        name=rule_name,
        origin="extracted",
        schema_version=1,
        source_url=job.final_url or job.source_url,
        rules=validated_rules,
        provenance=prov,
        version=next_ver,
        is_active=True,
        lineage_id=root_id,
        source_text_hash=job.source_text_hash,
        created_from_extraction_id=job.extraction_id,
    )
    db.add(new_rule)
    db.flush()

    # 9. Update extraction job (GE-RS-17: clear source text, set confirmed_rule_id)
    job.confirmed_rule_id = new_rule.rule_id
    job.source_text = None

    # 10. Link project if given (GE-RS-15)
    domain = None
    if job.source_url:
        domain = urlparse(job.source_url).netloc

    if target_project:
        target_project.guideline_rule_id = new_rule.rule_id
        log_activity(db, current_user.user_id, target_project, "guideline_extracted", {"journalId": target_journal_id, "domain": domain})
        log_activity(db, current_user.user_id, target_project, "guideline_rules_linked", {"ruleId": new_rule.rule_id})

    # Log rules saved
    log_activity(
        db,
        current_user.user_id,
        target_project,
        "guideline_rules_saved",
        {
            "ruleId": new_rule.rule_id,
            "journalId": target_journal_id,
            "version": next_ver,
            "origin": "extracted",
            "domain": domain,
        },
    )

    db.commit()
    db.refresh(new_rule)
    return build_ruleset_response(new_rule)


@router.post("/rule-sets", status_code=status.HTTP_201_CREATED, response_model=RuleSetOut)
def create_rule_set_manual(
    data: RuleSetCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually creates a new rule set.
    Reference: Section 7.6, 10.13 (GE-RS-20, GE-RS-21).
    """
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")
    if len(data.name.strip()) > 200:
        raise HTTPException(status_code=422, detail="Name must not exceed 200 characters.")

    target_journal_id = None
    if data.journal_id is not None:
        try:
            target_journal_id = int(data.journal_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Journal not found")
        journal = db.get(Journal, target_journal_id)
        if not journal:
            raise HTTPException(status_code=404, detail="Journal not found")

    try:
        validated_rules = validate_rules_payload(data.rules)
    except RuleValidationError as rve:
        if rve.code == "NO_RULES":
            raise HTTPException(status_code=422, detail={"code": "NO_RULES", "message": rve.message})
        raise HTTPException(status_code=422, detail=rve.errors or rve.message)

    root_id = None
    next_ver = 1
    if target_journal_id:
        existing = db.scalars(
            select(GuidelineRule)
            .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == target_journal_id)
            .order_by(desc(GuidelineRule.version))
        ).all()
        if existing:
            root_id = existing[0].lineage_id or existing[0].rule_id
            next_ver = max(r.version for r in existing) + 1
            db.execute(
                update(GuidelineRule)
                .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == target_journal_id)
                .values(is_active=False)
            )

    new_rule = GuidelineRule(
        owner_user_id=current_user.user_id,
        journal_id=target_journal_id,
        name=data.name.strip(),
        origin="manual",
        schema_version=1,
        source_url=data.source_url,
        rules=validated_rules,
        provenance={"manual": True},
        version=next_ver,
        is_active=True,
        lineage_id=root_id,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    log_activity(
        db,
        current_user.user_id,
        None,
        "guideline_rules_saved",
        {
            "ruleId": new_rule.rule_id,
            "journalId": target_journal_id,
            "version": next_ver,
            "origin": "manual",
        },
    )
    return build_ruleset_response(new_rule)


@router.get("/rule-sets", response_model=RuleSetListOut)
def list_rule_sets(
    journal_id: str | None = Query(default=None, alias="journalId"),
    is_active: bool | None = Query(default=None, alias="isActive"),
    origin: str | None = None,
    scope: Literal["mine", "system", "all"] = "all",
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists rule sets visible to the user (mine plus system ones; never another user's).
    Reference: Section 10.13 (GE-RS-22, GE-RS-23).
    """
    offset = (page - 1) * page_size

    # Scope condition
    if scope == "mine":
        base_cond = (GuidelineRule.owner_user_id == current_user.user_id)
    elif scope == "system":
        base_cond = (GuidelineRule.owner_user_id.is_(None))
    else:
        base_cond = or_(
            GuidelineRule.owner_user_id == current_user.user_id,
            GuidelineRule.owner_user_id.is_(None),
        )

    q = select(GuidelineRule).where(base_cond)

    if journal_id is not None:
        try:
            jid = int(journal_id)
            q = q.where(GuidelineRule.journal_id == jid)
        except ValueError:
            pass

    if is_active is not None:
        q = q.where(GuidelineRule.is_active == is_active)

    if origin is not None:
        q = q.where(GuidelineRule.origin == origin)

    if search is not None and search.strip():
        q = q.where(GuidelineRule.name.ilike(f"%{search.strip()}%"))

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(q.order_by(desc(GuidelineRule.created_at)).offset(offset).limit(page_size)).all()

    return RuleSetListOut(
        items=[build_ruleset_response(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/rule-sets/{rule_id}", response_model=RuleSetOut)
def get_rule_set(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gets a rule set by ID (own or system; foreign -> 404)."""
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    return build_ruleset_response(rule)


@router.patch("/rule-sets/{rule_id}", response_model=RuleSetOut)
def patch_rule_set(
    rule_id: str,
    data: RuleSetPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edits a rule set.
    If rules change: creates a new active version in the same lineage.
    If only name changes: renames in-place.
    If identical: returns current version.
    Reference: Section 7.6, 10.13 (GE-RS-25 to GE-RS-30).
    """
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    if rule.owner_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system rule sets. Copy to customize.",
        )

    if data.name is not None and len(data.name.strip()) > 200:
        raise HTTPException(status_code=422, detail="Name must not exceed 200 characters.")

    # Check what changed
    rules_changed = False
    validated_rules = None
    if data.rules is not None:
        try:
            validated_rules = validate_rules_payload(data.rules)
        except RuleValidationError as rve:
            if rve.code == "NO_RULES":
                raise HTTPException(status_code=422, detail={"code": "NO_RULES", "message": rve.message})
            raise HTTPException(status_code=422, detail=rve.errors or rve.message)
        rules_changed = (validated_rules != (rule.rules or {}))

    name_changed = (data.name is not None and data.name.strip() != rule.name)

    if not rules_changed and not name_changed:
        return build_ruleset_response(rule)

    if not rules_changed and name_changed:
        # In-place rename (GE-RS-30)
        rule.name = data.name.strip()
        rule.updated_at = func.now()
        db.commit()
        db.refresh(rule)
        return build_ruleset_response(rule)

    # Rules changed: create a new active version in the lineage (GE-RS-25)
    root_id = rule.lineage_id or rule.rule_id
    all_versions = db.scalars(
        select(GuidelineRule).where(or_(GuidelineRule.lineage_id == root_id, GuidelineRule.rule_id == root_id))
    ).all()
    next_ver = max(r.version for r in all_versions) + 1

    # Deactivate existing active versions in lineage
    db.execute(
        update(GuidelineRule)
        .where(or_(GuidelineRule.lineage_id == root_id, GuidelineRule.rule_id == root_id))
        .values(is_active=False)
    )
    if rule.journal_id:
        db.execute(
            update(GuidelineRule)
            .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == rule.journal_id)
            .values(is_active=False)
        )

    new_prov = build_ruleset_provenance(None, validated_rules, previous_provenance=rule.provenance)
    new_rule = GuidelineRule(
        owner_user_id=current_user.user_id,
        journal_id=rule.journal_id,
        name=data.name.strip() if (data.name and data.name.strip()) else rule.name,
        origin=rule.origin,
        schema_version=1,
        source_url=rule.source_url,
        rules=validated_rules,
        provenance=new_prov,
        version=next_ver,
        is_active=True,
        lineage_id=root_id,
        source_text_hash=rule.source_text_hash,
        created_from_extraction_id=rule.created_from_extraction_id,
    )
    db.add(new_rule)
    db.flush()

    # Automatically update projects pointing to this lineage to the new active version (GE-LNK-08)
    lineage_ids = [r.rule_id for r in all_versions]
    db.execute(
        update(Project)
        .where(Project.user_id == current_user.user_id, Project.guideline_rule_id.in_(lineage_ids))
        .values(guideline_rule_id=new_rule.rule_id)
    )

    log_activity(
        db,
        current_user.user_id,
        None,
        "guideline_rules_saved",
        {
            "ruleId": new_rule.rule_id,
            "journalId": rule.journal_id,
            "version": next_ver,
            "origin": rule.origin,
        },
    )

    db.commit()
    db.refresh(new_rule)
    return build_ruleset_response(new_rule)


@router.get("/rule-sets/{rule_id}/versions", response_model=list[RuleSetOut])
def list_rule_set_versions(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists all versions in this rule set's lineage in version order."""
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    root_id = rule.lineage_id or rule.rule_id
    versions = db.scalars(
        select(GuidelineRule)
        .where(or_(GuidelineRule.lineage_id == root_id, GuidelineRule.rule_id == root_id))
        .order_by(GuidelineRule.version.asc())
    ).all()

    return [build_ruleset_response(v) for v in versions]


@router.post("/rule-sets/{rule_id}/activate", response_model=RuleSetOut)
def activate_rule_set_version(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activates an older version in the lineage, deactivating others.
    Updates projects using this lineage to point to the newly activated version.
    Reference: Section 10.13 (GE-RS-32, GE-RS-33).
    """
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    if rule.owner_user_id is None:
        raise HTTPException(status_code=403, detail="Cannot activate or deactivate system rule sets.")

    if rule.is_active:
        return build_ruleset_response(rule)

    root_id = rule.lineage_id or rule.rule_id
    db.execute(
        update(GuidelineRule)
        .where(or_(GuidelineRule.lineage_id == root_id, GuidelineRule.rule_id == root_id))
        .values(is_active=False)
    )
    if rule.journal_id:
        db.execute(
            update(GuidelineRule)
            .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == rule.journal_id)
            .values(is_active=False)
        )

    rule.is_active = True
    rule.updated_at = func.now()

    all_versions = db.scalars(
        select(GuidelineRule.rule_id).where(or_(GuidelineRule.lineage_id == root_id, GuidelineRule.rule_id == root_id))
    ).all()
    db.execute(
        update(Project)
        .where(Project.user_id == current_user.user_id, Project.guideline_rule_id.in_(all_versions))
        .values(guideline_rule_id=rule.rule_id)
    )

    db.commit()
    db.refresh(rule)
    return build_ruleset_response(rule)


@router.post("/rule-sets/{rule_id}/copy", status_code=status.HTTP_201_CREATED, response_model=RuleSetOut)
def copy_rule_set(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Copies a system or own rule set into a new independent lineage owned by the current user.
    Reference: Section 10.13 (GE-RS-34, GE-RS-35, GE-RS-36).
    """
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    source_rule = db.get(GuidelineRule, rid)
    if not source_rule or (source_rule.owner_user_id is not None and source_rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    # If copying for a journal where user already has an active rule set, deactivate it (GE-RS-36)
    if source_rule.journal_id:
        db.execute(
            update(GuidelineRule)
            .where(GuidelineRule.owner_user_id == current_user.user_id, GuidelineRule.journal_id == source_rule.journal_id)
            .values(is_active=False)
        )

    new_rule = GuidelineRule(
        owner_user_id=current_user.user_id,
        journal_id=source_rule.journal_id,
        name=f"{source_rule.name} (Copy)"[:200],
        origin="manual",
        schema_version=source_rule.schema_version,
        source_url=source_rule.source_url,
        rules=dict(source_rule.rules or {}),
        provenance={"copiedFrom": source_rule.rule_id},
        version=1,
        is_active=True,
        lineage_id=None,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    return build_ruleset_response(new_rule)


@router.delete("/rule-sets/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_set(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes one version of an owned rule set (system -> 403, foreign -> 404).
    If a project used it, project.guideline_rule_id becomes null.
    Reference: Section 10.13 (GE-RS-37 to GE-RS-41).
    """
    try:
        rid = int(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    if rule.owner_user_id is None:
        raise HTTPException(status_code=403, detail="Cannot delete system rule sets.")

    # Unlink any projects pointing to this rule set (GE-RS-40)
    db.execute(
        update(Project)
        .where(Project.guideline_rule_id == rule.rule_id)
        .values(guideline_rule_id=None)
    )

    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# Catalog Journal Effective Guidelines
# ===========================================================================

@journals_guidelines_router.get("/{journal_id}/guidelines", response_model=JournalEffectiveRulesOut)
def get_journal_effective_guidelines(
    journal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns effective rule set for a catalog journal:
    user's active rule set > system active rule set > null.
    Reference: Section 10.13 (GE-RS-46 to GE-RS-49).
    """
    try:
        jid = int(journal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Journal not found")

    journal = db.get(Journal, jid)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")

    rule, source = resolve_effective_rule_for_journal(db, current_user.user_id, jid)
    return JournalEffectiveRulesOut(
        rule_set=build_ruleset_response(rule) if rule else None,
        source=source,
    )


# ===========================================================================
# Project Guidelines Link (Phase G9)
# ===========================================================================

@projects_guidelines_router.put("/{project_id}/guidelines/{rule_set_id}", response_model=RuleSetOut)
def link_project_guideline_rule(
    project_id: str,
    rule_set_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Links a rule set (own or system) to a project.
    Reference: Section 10.14 (GE-LNK-01 to GE-LNK-04).
    """
    try:
        pid = int(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    project = db.get(Project, pid)
    if not project or project.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        rid = int(rule_set_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    rule = db.get(GuidelineRule, rid)
    if not rule or (rule.owner_user_id is not None and rule.owner_user_id != current_user.user_id):
        raise HTTPException(status_code=404, detail="Guideline rule set not found")

    project.guideline_rule_id = rule.rule_id
    log_activity(db, current_user.user_id, project, "guideline_rules_linked", {"ruleId": rule.rule_id})
    db.commit()
    db.refresh(rule)

    return build_ruleset_response(rule)


@projects_guidelines_router.delete("/{project_id}/guidelines", status_code=status.HTTP_204_NO_CONTENT)
def unlink_project_guideline_rule(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unlinks the project's explicit rule set.
    Reference: Section 10.14 (GE-LNK-05).
    """
    try:
        pid = int(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    project = db.get(Project, pid)
    if not project or project.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.guideline_rule_id:
        old_id = project.guideline_rule_id
        project.guideline_rule_id = None
        log_activity(db, current_user.user_id, project, "guideline_rules_unlinked", {"ruleId": old_id})
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@projects_guidelines_router.get("/{project_id}/guidelines", response_model=JournalEffectiveRulesOut)
def get_project_effective_guidelines(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gets the project's effective rule set and its resolution source:
    project link > target journal user rule > target journal system rule > null.
    Reference: Section 10.14 (GE-LNK-06, GE-LNK-07).
    """
    try:
        pid = int(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    project = db.get(Project, pid)
    if not project or project.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    rule, source = resolve_effective_rule_for_project(db, project)
    return JournalEffectiveRulesOut(
        rule_set=build_ruleset_response(rule) if rule else None,
        source=source,
    )
