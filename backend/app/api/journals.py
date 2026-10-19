import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.journal import Journal
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.journal import JournalBrowseResponse, JournalItemOut

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
    quartile: Optional[str] = Query(None, description="Filter by quartile (Q1, Q2, Q3, Q4)"),
    publisher: Optional[str] = Query(None, description="Filter by publisher"),
    open_access_type: Optional[str] = Query(None, description="Filter by open access type"),
    sort_by: str = Query("title", description="Sort by: title, citescore, impact_factor, review_weeks, acceptance_rate"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JournalBrowseResponse:
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
    if category and category.strip() and category.lower() != "all":
        query = query.where(Journal.subject_category == category.strip())

    if quartile and quartile.strip() and quartile.lower() != "all":
        query = query.where(Journal.quartile == quartile.strip().upper())

    if publisher and publisher.strip() and publisher.lower() != "all":
        query = query.where(Journal.publisher.ilike(f"%{publisher.strip()}%"))

    if open_access_type and open_access_type.strip() and open_access_type.lower() != "all":
        query = query.where(Journal.open_access_type.ilike(f"%{open_access_type.strip()}%"))

    # Count total matching records
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar_one()

    # 3. Sorting
    sort_column_map = {
        "title": Journal.journal_title,
        "citescore": Journal.citescore,
        "impact_factor": Journal.impact_factor,
        "review_weeks": Journal.review_weeks,
        "acceptance_rate": Journal.acceptance_rate,
        "quartile": Journal.quartile,
    }
    sort_col = sort_column_map.get(sort_by.lower(), Journal.journal_title)

    if sort_order.lower() == "desc":
        query = query.order_by(sort_col.desc().nulls_last())
    else:
        query = query.order_by(sort_col.asc().nulls_last())

    # 4. Pagination
    offset_val = (page - 1) * limit
    paginated_query = query.offset(offset_val).limit(limit)
    journals_rows = db.execute(paginated_query).scalars().all()

    total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

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
        limit=limit,
        total_pages=total_pages,
        categories=categories,
        publishers=publishers,
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
