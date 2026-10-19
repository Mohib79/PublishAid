import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.journal import Journal

logger = logging.getLogger(__name__)


def build_query_text(
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> str:
    """Combines user input title, abstract, and keywords into a single SPECTER-ready query string."""
    clean_title = (title or "").strip()
    clean_abstract = (abstract or "").strip()

    parts: list[str] = []
    if clean_title:
        parts.append(clean_title)
    if clean_abstract:
        parts.append(clean_abstract)

    if keywords:
        clean_kw = [k.strip() for k in keywords if k and k.strip()]
        if clean_kw:
            parts.append("Keywords: " + ", ".join(clean_kw))

    return ". ".join(parts)


def to_match_score(similarity: float) -> int:
    """Converts cosine similarity (0.0 to 1.0) into user-facing percentage score (0 to 100)."""
    # Clamp between 0.0 and 1.0 before scaling
    clamped = max(0.0, min(1.0, float(similarity)))
    return int(round(clamped * 100))


def search_matching_journals(
    query_vector: list[float],
    db: Session,
    limit: int = 20,
) -> list[tuple[Journal, float, int, Optional[str]]]:
    """
    Executes cosine distance search in pgvector over indexed journals.
    Returns list of tuples: (journal, raw_similarity, match_score, match_tag)
    """
    distance = Journal.embedding.cosine_distance(query_vector)

    stmt = (
        select(Journal, (1 - distance).label("similarity"))
        .where(Journal.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(limit)
    )

    rows = db.execute(stmt).all()
    results: list[tuple[Journal, float, int, Optional[str]]] = []

    for rank, row in enumerate(rows, start=1):
        journal: Journal = row[0]
        raw_sim = float(row[1]) if row[1] is not None else 0.0
        score = to_match_score(raw_sim)
        tag = "Best fit" if rank == 1 else None
        results.append((journal, raw_sim, score, tag))

    return results
