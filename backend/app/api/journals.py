import math
import re
import time
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.journal import (
    JournalBrowseResponse,
    JournalCompareResponse,
    JournalItemOut,
    MatchJournalItemOut,
    MatchMeta,
    MatchRequest,
    MatchResponse,
)
from app.services.comparison.registry import build_comparison_payload
from app.services.embedding import EmbedderProtocol, get_embedder
from app.services.guidelines.ruleset_service import resolve_effective_rules_for_journals
from app.services.matching import (
    build_query_text,
    search_matching_journals,
    to_match_score,
)

router = APIRouter(prefix="/journals", tags=["journals"])


@router.get(
    "",
    response_model=JournalBrowseResponse,
    summary="Filter and browse journal catalog",
)
@router.get(
    "/browse",
    response_model=JournalBrowseResponse,
    summary="Filter and browse journal catalog (SRS / Architecture alias)",
)
def browse_journals(
    search: Optional[str] = Query(None, description="Search by title, publisher, subject, or ISSN"),
    category: Optional[str] = Query(None, description="Filter by subject category"),
    subject_category: Optional[str] = Query(None, alias="subjectCategory", description="Alias for category"),
    quartile: Optional[str] = Query(None, description="Filter by quartile (Q1, Q2, Q3, Q4)"),
    publisher: Optional[str] = Query(None, description="Filter by publisher"),
    open_access_type: Optional[str] = Query(None, description="Filter by open access type"),
    open_access: Optional[str] = Query(None, alias="openAccess", description="Alias for open_access_type"),
    sort_by: str = Query("title", description="Sort by: title, citescore, impact_factor, review_weeks, acceptance_rate, quartile"),
    sort: Optional[str] = Query(None, description="Alias for sort_by"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    order: Optional[str] = Query(None, description="Alias for sort_order"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    page_size: Optional[int] = Query(None, alias="pageSize", ge=1, le=100, description="Alias for limit"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalBrowseResponse:
    effective_category = category if category is not None else subject_category
    effective_oa = open_access_type if open_access_type is not None else open_access
    effective_sort_by = sort if sort is not None else sort_by
    effective_sort_order = order if order is not None else sort_order
    effective_limit = page_size if page_size is not None else limit

    # Validate sort and order before executing query
    sort_column_map = {
        "title": Journal.journal_title,
        "citescore": Journal.citescore,
        "impact_factor": Journal.impact_factor,
        "impactfactor": Journal.impact_factor,
        "review_weeks": Journal.review_weeks,
        "reviewweeks": Journal.review_weeks,
        "acceptance_rate": Journal.acceptance_rate,
        "acceptancerate": Journal.acceptance_rate,
        "quartile": Journal.quartile,
    }
    sort_key = effective_sort_by.strip().lower()
    if sort_key not in sort_column_map:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort field: {effective_sort_by}",
        )
    order_key = effective_sort_order.strip().lower()
    if order_key not in ("asc", "desc"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sort order must be 'asc' or 'desc'",
        )

    query = select(Journal)

    # 1. Search term filter across relevant text columns
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Journal.journal_title.ilike(term),
                Journal.publisher.ilike(term),
                Journal.subject_category.ilike(term),
                Journal.issn.ilike(term),
                Journal.aims_and_scope.ilike(term),
            )
        )

    # 2. Categorical filters
    if effective_category and effective_category.strip() and effective_category.lower() != "all":
        query = query.where(Journal.subject_category == effective_category.strip())

    if quartile and quartile.strip() and quartile.lower() != "all":
        query = query.where(Journal.quartile == quartile.strip().upper())

    if publisher and publisher.strip() and publisher.lower() != "all":
        query = query.where(Journal.publisher.ilike(f"%{publisher.strip()}%"))

    if effective_oa and effective_oa.strip() and effective_oa.lower() != "all":
        query = query.where(Journal.open_access_type.ilike(f"%{effective_oa.strip()}%"))

    # Count total matching records
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar_one()

    # 3. Sorting
    sort_col = sort_column_map[sort_key]

    if order_key == "desc":
        query = query.order_by(sort_col.desc().nulls_last(), Journal.journal_id.asc())
    else:
        query = query.order_by(sort_col.asc().nulls_last(), Journal.journal_id.asc())

    # 4. Pagination
    offset_val = (page - 1) * effective_limit
    paginated_query = query.offset(offset_val).limit(effective_limit)
    journals_rows = db.execute(paginated_query).scalars().all()

    total_pages = max(1, math.ceil(total / effective_limit)) if total > 0 else 1

    # 5. Fetch distinct categories and publishers for filter options
    categories_raw = db.execute(
        select(Journal.subject_category)
        .where(Journal.subject_category.is_not(None))
        .distinct()
        .order_by(Journal.subject_category)
    ).scalars().all()
    categories = [cat for cat in categories_raw if cat]

    publishers_raw = db.execute(
        select(Journal.publisher)
        .where(Journal.publisher.is_not(None))
        .distinct()
        .order_by(Journal.publisher)
    ).scalars().all()
    publishers = [pub for pub in publishers_raw if pub]

    items = [JournalItemOut.model_validate(j) for j in journals_rows]

    return JournalBrowseResponse(
        items=items,
        total=total,
        page=page,
        limit=effective_limit,
        total_pages=total_pages,
        categories=categories,
        publishers=publishers,
    )


@router.get(
    "/compare",
    response_model=JournalCompareResponse,
    summary="Compare 2 to 4 journals side by side",
)
def compare_journals(
    ids: Optional[str] = Query(None, description="Comma-separated positive integer journal IDs (2 to 4 unique)"),
    project_id: Optional[str] = Query(None, alias="projectId", description="Optional project ID for match scores and shortlist status"),
    include: Optional[str] = Query(None, description="Optional extra groups, e.g. 'requirements'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if ids is None or not ids.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 journal IDs are required for comparison.",
        )

    raw_splits = ids.split(",")
    if len(raw_splits) > 40:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At most 20 raw journal IDs are allowed.",
        )

    raw_tokens = [tok.strip() for tok in raw_splits if tok.strip()]
    if len(raw_tokens) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At most 20 raw journal IDs are allowed.",
        )

    if not raw_tokens:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 journal IDs are required for comparison.",
        )

    parsed_ids: list[int] = []
    for tok in raw_tokens:
        if not re.fullmatch(r"[0-9]+", tok):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid journal ID: '{tok}'. IDs must be positive integers.",
            )
        val = int(tok)
        if val <= 0 or val > 2147483647:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Journal ID out of range: '{tok}'.",
            )
        parsed_ids.append(val)

    unique_ids = list(dict.fromkeys(parsed_ids))
    if len(unique_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 unique journals are required for comparison.",
        )
    if len(unique_ids) > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At most 4 journals can be compared at one time.",
        )

    include_requirements = False
    if include is not None and include.strip():
        inc_tokens = [t.strip() for t in include.split(",") if t.strip()]
        for tok in inc_tokens:
            if tok != "requirements":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unsupported include value: '{tok}'.",
                )
            include_requirements = True

    include_fit = False
    verified_project_id: Optional[int] = None
    if project_id is not None and project_id.strip():
        pid_str = project_id.strip()
        if not re.fullmatch(r"[0-9]+", pid_str):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        p_id = int(pid_str)
        if p_id <= 0 or p_id > 2147483647:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        project = db.execute(
            select(Project).where(
                Project.project_id == p_id,
                Project.user_id == current_user.user_id,
            )
        ).scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        include_fit = True
        verified_project_id = project.project_id

    # 1. Fetch journals in a single query and preserve requested ID order
    journal_rows = db.execute(
        select(Journal).where(Journal.journal_id.in_(unique_ids))
    ).scalars().all()
    journal_map = {j.journal_id: j for j in journal_rows}

    missing_ids = [str(jid) for jid in unique_ids if jid not in journal_map]
    if missing_ids:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Journal not found", "missingIds": missing_ids},
        )

    ordered_journals = [journal_map[jid] for jid in unique_ids]

    # 2. Fetch project context in a single query if projectId was provided
    project_ctx_map: dict[int, dict[str, Any]] = {}
    if include_fit and verified_project_id is not None:
        pj_rows = db.execute(
            select(ProjectJournal).where(
                ProjectJournal.project_id == verified_project_id,
                ProjectJournal.journal_id.in_(unique_ids),
            )
        ).scalars().all()
        for pj in pj_rows:
            raw_sim = float(pj.similarity_score) if pj.similarity_score is not None else None
            match_score = to_match_score(raw_sim) if raw_sim is not None else None
            project_ctx_map[pj.journal_id] = {
                "isShortlisted": bool(pj.is_shortlisted),
                "isTarget": bool(pj.is_selected),
                "rawSimilarity": round(raw_sim, 4) if raw_sim is not None else None,
                "matchScore": match_score,
            }

    # 3. Batch-resolve effective rules in a single query if requested (Part B)
    req_ctx_map: dict[int, tuple[Any, str | None]] = {}
    if include_requirements:
        req_ctx_map = resolve_effective_rules_for_journals(
            db, current_user.user_id, unique_ids
        )

    return build_comparison_payload(
        ordered_journals,
        project_ctx_map=project_ctx_map,
        include_fit=include_fit,
        req_ctx_map=req_ctx_map,
        include_requirements=include_requirements,
    )


@router.get(
    "/{journal_id}",
    response_model=JournalItemOut,
    summary="Get single journal profile details",
)
def get_journal(
    journal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalItemOut:
    journal = db.execute(
        select(Journal).where(Journal.journal_id == journal_id)
    ).scalar_one_or_none()

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal with ID {journal_id} not found",
        )

    return JournalItemOut.model_validate(journal)


@router.post(
    "/match",
    response_model=MatchResponse,
    summary="Rank journals by semantic similarity with manuscript title and abstract",
)
def match_journals(
    req: MatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    embedder: EmbedderProtocol = Depends(get_embedder),
) -> MatchResponse:
    shortlisted_journal_ids: set[int] = set()

    # Check project ownership if project_id is supplied
    if req.project_id is not None:
        try:
            p_id = int(req.project_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        project = db.execute(
            select(Project).where(
                Project.project_id == p_id,
                Project.user_id == current_user.user_id,
            )
        ).scalar_one_or_none()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        pj_rows = db.execute(
            select(ProjectJournal.journal_id).where(
                ProjectJournal.project_id == p_id,
                ProjectJournal.is_shortlisted.is_(True),
            )
        ).scalars().all()
        shortlisted_journal_ids = set(pj_rows)

    start_time = time.perf_counter()

    # 1. Build SPECTER-aligned query text
    query_text = build_query_text(
        title=req.title,
        abstract=req.abstract,
        keywords=req.keywords if isinstance(req.keywords, list) else None,
    )

    # 2. Compute query embedding vector
    query_vector = embedder.embed_query(query_text)

    # 3. Perform pgvector cosine distance search
    matched_records = search_matching_journals(
        query_vector=query_vector,
        db=db,
        limit=req.limit,
    )

    # 4. Count total active embedded journals
    total_journals = db.execute(
        select(func.count(Journal.journal_id)).where(Journal.embedding.is_not(None))
    ).scalar_one()

    took_ms = max(1, int((time.perf_counter() - start_time) * 1000))

    # 5. Format results
    results: list[MatchJournalItemOut] = []
    for journal, raw_sim, score, tag in matched_records:
        is_short = journal.journal_id in shortlisted_journal_ids
        item_dict = JournalItemOut.model_validate(journal).model_dump(by_alias=True)
        item_dict.update({
            "matchScore": score,
            "rawSimilarity": round(raw_sim, 4),
            "matchTag": tag,
            "isShortlisted": is_short,
        })
        results.append(MatchJournalItemOut.model_validate(item_dict))

    return MatchResponse(
        results=results,
        meta=MatchMeta(
            model=settings.EMBEDDING_MODEL,
            took_ms=took_ms,
            total_journals=total_journals,
        ),
    )
