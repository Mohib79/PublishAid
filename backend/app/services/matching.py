"""Hybrid journal matching service combining vectorized cosine similarity and Okapi BM25."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings_config import build_journal_lexical_text, normalize_whitespace
from app.db.models.journal import Journal
from app.services.bm25 import BM25Index

logger = logging.getLogger(__name__)


@dataclass
class JournalMatchResult:
    journal: Journal
    raw_cosine: float
    bm25_score: float
    hybrid_score: float
    match_score: int
    match_tag: Optional[str] = None


def build_query_text(
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> str:
    """Combines user input title, abstract, and keywords into natural-language prose for embedding."""
    clean_title = normalize_whitespace(title)
    clean_abstract = normalize_whitespace(abstract)

    parts: list[str] = []
    if clean_title:
        parts.append(clean_title)
    if clean_abstract:
        parts.append(clean_abstract)

    if keywords:
        clean_kw = [normalize_whitespace(k) for k in keywords if normalize_whitespace(k)]
        if clean_kw:
            parts.append("Keywords: " + ", ".join(clean_kw))

    out = ""
    for part in parts:
        if not out:
            out = part
        elif out.endswith((".", "!", "?")):
            out = f"{out} {part}"
        else:
            out = f"{out}. {part}"
    return out


def to_match_score(similarity: float) -> int:
    """
    Calibrates a standalone cosine similarity score into a 0-100 percentage score
    using empirical bounds for all-mpnet-base-v2 embeddings [0.0, 0.90].
    """
    sim = float(similarity)
    t_min = 0.0
    t_max = 0.90

    if sim <= t_min:
        return 0
    if sim >= t_max:
        return 100

    scaled = ((sim - t_min) / (t_max - t_min)) * 100.0
    return int(round(scaled))


def normalize_cosine_for_hybrid(
    cosine_scores: np.ndarray,
    min_span: float = 0.25,
) -> np.ndarray:
    """
    Min-max normalizes cosine similarity across the candidate pool into [0.0, 1.0]
    with a minimum span floor so tiny score gaps in small pools are not over-amplified.
    """
    if cosine_scores.size == 0:
        return np.zeros(0, dtype=np.float64)
    if cosine_scores.size == 1:
        return np.clip(cosine_scores, 0.0, 1.0)
    c_max = float(cosine_scores.max())
    c_min = float(cosine_scores.min())
    span = max(c_max - c_min, min_span)
    floor = c_max - span
    return np.clip((cosine_scores - floor) / span, 0.0, 1.0)


def compute_relative_match_scores(
    hybrid_scores: np.ndarray,
    cosine_scores: np.ndarray,
) -> list[int]:
    """
    Computes 0-100 display scores that preserve hybrid ranking order while anchoring
    the top percentage to the pool's empirical raw cosine similarity range [0.05, 0.44]
    for all-mpnet-base-v2 asymmetric retrieval.
    """
    n = int(len(hybrid_scores))
    if n == 0:
        return []
    if n == 1:
        cos0 = float(cosine_scores[0])
        return [100] if cos0 >= 0.99 else [to_match_score(cos0)]

    max_cos = float(cosine_scores.max())
    if max_cos <= 0.0:
        return [0] * n

    cos_floor = 0.05
    cos_ceil = 0.44
    high_target = min(96.0, max(5.0, ((max_cos - cos_floor) / (cos_ceil - cos_floor)) * 95.0))

    min_s = float(hybrid_scores.min())
    max_s = float(hybrid_scores.max())
    if max_s <= min_s:
        return [
            100 if float(c) >= 0.99 else min(96, max(0, int(round(high_target))))
            for c in cosine_scores
        ]

    min_cos = max(cos_floor, float(cosine_scores.min()))
    low_target = min(
        high_target * 0.4,
        max(5.0, ((min_cos - cos_floor) / (cos_ceil - cos_floor)) * 95.0),
    )

    scores: list[int] = []
    for h, c in zip(hybrid_scores, cosine_scores):
        if float(c) >= 0.99:
            scores.append(100)
            continue
        ratio = (float(h) - min_s) / (max_s - min_s)
        scaled = low_target + ratio * (high_target - low_target)
        scores.append(max(0, min(96, int(round(scaled)))))
    return scores


def compute_vectorized_cosine_similarity(
    doc_matrix: np.ndarray,
    query_vector: np.ndarray,
) -> np.ndarray:
    """Computes cosine similarity across all pre-computed journal vectors via vectorized NumPy math."""
    if doc_matrix.size == 0:
        return np.zeros(0, dtype=np.float64)

    q_norm = float(np.linalg.norm(query_vector))
    if q_norm == 0.0:
        return np.zeros(doc_matrix.shape[0], dtype=np.float64)

    doc_norms = np.linalg.norm(doc_matrix, axis=1)
    denom = np.maximum(doc_norms * q_norm, 1e-12)
    return (doc_matrix @ query_vector) / denom


def search_matching_journals(
    query_vector: list[float],
    db: Session,
    query_text: str = "",
    limit: int = 10,
    cosine_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> list[JournalMatchResult]:
    """
    Ranks all embedded journals in the database using vectorized NumPy cosine similarity
    combined with normalized Okapi BM25 lexical scores (no LLM API calls).
    """
    journals = db.execute(
        select(Journal).where(Journal.embedding.is_not(None))
    ).scalars().all()

    if not journals:
        return []

    w_cos = settings.HYBRID_COSINE_WEIGHT if cosine_weight is None else cosine_weight
    w_bm25 = settings.HYBRID_BM25_WEIGHT if bm25_weight is None else bm25_weight

    doc_matrix = np.asarray([list(j.embedding) for j in journals], dtype=np.float64)
    q_vec = np.asarray(query_vector, dtype=np.float64)

    cosine_scores = compute_vectorized_cosine_similarity(doc_matrix, q_vec)

    if query_text and query_text.strip() and w_bm25 > 0.0:
        lexical_docs = [
            build_journal_lexical_text(j.journal_title, j.aims_and_scope, j.subject_category)
            for j in journals
        ]
        bm25_scores = BM25Index(lexical_docs).normalized_score(query_text)
        norm_cosine_scores = normalize_cosine_for_hybrid(cosine_scores)
    else:
        bm25_scores = np.zeros(len(journals), dtype=np.float64)
        norm_cosine_scores = cosine_scores

    hybrid_scores = (w_cos * norm_cosine_scores) + (w_bm25 * bm25_scores)
    match_scores = compute_relative_match_scores(hybrid_scores, cosine_scores)

    sorted_indices = sorted(
        range(len(journals)),
        key=lambda idx: (-float(hybrid_scores[idx]), -float(cosine_scores[idx]), journals[idx].journal_id),
    )

    results: list[JournalMatchResult] = []
    for rank, idx in enumerate(sorted_indices[:limit], start=1):
        results.append(
            JournalMatchResult(
                journal=journals[idx],
                raw_cosine=float(cosine_scores[idx]),
                bm25_score=float(bm25_scores[idx]),
                hybrid_score=float(hybrid_scores[idx]),
                match_score=match_scores[idx],
                match_tag="Best fit" if rank == 1 else None,
            )
        )

    return results
