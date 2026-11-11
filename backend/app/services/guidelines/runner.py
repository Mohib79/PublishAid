"""
Background Extraction Job Runner, Quota Enforcer, Caching, and Lifecycle Management.
Reference: Guideline Extraction Plan Section 7.5, 10.12 (GE-JOB).
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
import logging
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from app.db.models.guideline_extraction import GuidelineExtraction
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.services.activity import log_activity
from app.services.guidelines.fetcher import safe_fetch_url, FetchError
from app.services.guidelines.cleaner import (
    clean_guideline_content,
    detect_guideline_language,
    count_words,
    CleanError,
)
from app.services.guidelines.chunker import build_text_chunks
from app.services.guidelines.extractor import orchestrate_extraction
from app.services.guidelines.llm.base import BaseLLMClient, LLMError
from app.services.guidelines.llm.fake_client import FakeLLMClient
from app.services.guidelines.llm.gemini_client import GeminiLLMClient

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS_PER_USER = 2
MAX_DAILY_LLM_JOBS_PER_USER = 20
STUCK_JOB_TIMEOUT_MINUTES = 10

# Test client override for testing offline with FakeLLMClient
_GLOBAL_LLM_CLIENT: BaseLLMClient | None = None


def set_global_llm_client(client: BaseLLMClient | None) -> None:
    """Sets a global test LLM client override (e.g. FakeLLMClient)."""
    global _GLOBAL_LLM_CLIENT
    _GLOBAL_LLM_CLIENT = client


def get_llm_client() -> BaseLLMClient:
    """Returns active LLM client (override or real Gemini client)."""
    if _GLOBAL_LLM_CLIENT is not None:
        return _GLOBAL_LLM_CLIENT
    return GeminiLLMClient()


class QuotaError(Exception):
    def __init__(self, code: str, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


def check_and_enforce_quotas(db: Session, user_id: int) -> None:
    """
    Enforces user quotas:
    - At most 2 queued or running jobs per user (429 TOO_MANY_RUNNING)
    - At most 20 jobs reaching the LLM in rolling 24 hours (429 DAILY_LIMIT)
    """
    # 1. Concurrent running/queued jobs
    running_count = db.scalar(
        select(func.count(GuidelineExtraction.extraction_id)).where(
            GuidelineExtraction.user_id == user_id,
            GuidelineExtraction.status.in_(["queued", "running"]),
        )
    ) or 0

    if running_count >= MAX_CONCURRENT_JOBS_PER_USER:
        raise QuotaError("TOO_MANY_RUNNING", "You already have 2 extraction jobs queued or running.")

    # 2. Daily LLM jobs in rolling 24 hours (jobs where input_tokens > 0 or status == 'completed')
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    daily_llm_count = db.scalar(
        select(func.count(GuidelineExtraction.extraction_id)).where(
            GuidelineExtraction.user_id == user_id,
            GuidelineExtraction.created_at >= since_24h,
            or_(
                GuidelineExtraction.input_tokens > 0,
                and_(GuidelineExtraction.status == "completed", GuidelineExtraction.cached.is_(False)),
            ),
        )
    ) or 0

    if daily_llm_count >= MAX_DAILY_LLM_JOBS_PER_USER:
        # Calculate retry-after until oldest job in window rolls out
        oldest_job = db.scalar(
            select(GuidelineExtraction.created_at).where(
                GuidelineExtraction.user_id == user_id,
                GuidelineExtraction.created_at >= since_24h,
                GuidelineExtraction.input_tokens > 0,
            ).order_by(GuidelineExtraction.created_at.asc()).limit(1)
        )
        retry_seconds = 3600
        if oldest_job:
            window_end = oldest_job + timedelta(hours=24)
            retry_seconds = max(1, int((window_end - now).total_seconds()))

        raise QuotaError("DAILY_LIMIT", "Daily extraction limit of 20 jobs reached.", retry_after=retry_seconds)


def find_in_flight_duplicate(
    db: Session, user_id: int, source_type: str, url: str | None, text_hash: str | None
) -> GuidelineExtraction | None:
    """Finds an existing in-flight job for the same user with identical input."""
    q = select(GuidelineExtraction).where(
        GuidelineExtraction.user_id == user_id,
        GuidelineExtraction.source_type == source_type,
        GuidelineExtraction.status.in_(["queued", "running"]),
    )
    if source_type == "url" and url:
        q = q.where(GuidelineExtraction.source_url == url)
    elif source_type == "text" and text_hash:
        q = q.where(GuidelineExtraction.source_text_hash == text_hash)
    else:
        return None

    return db.scalars(q).first()


def find_cached_extraction(
    db: Session, user_id: int, text_hash: str, model_name: str, prompt_version: str = "v1"
) -> GuidelineExtraction | None:
    """Finds a completed extraction for the same user with identical text hash and model/prompt version."""
    return db.scalars(
        select(GuidelineExtraction).where(
            GuidelineExtraction.user_id == user_id,
            GuidelineExtraction.source_text_hash == text_hash,
            GuidelineExtraction.status == "completed",
            GuidelineExtraction.schema_version == 1,
            GuidelineExtraction.prompt_version == prompt_version,
            GuidelineExtraction.llm_model == model_name,
            GuidelineExtraction.draft.isnot(None),
        ).order_by(GuidelineExtraction.completed_at.desc())
    ).first()


def sweep_stuck_extractions(db: Session) -> int:
    """Marks extractions queued or running for > 10 minutes as failed with INTERRUPTED."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_JOB_TIMEOUT_MINUTES)
    stuck_jobs = db.scalars(
        select(GuidelineExtraction).where(
            GuidelineExtraction.status.in_(["queued", "running"]),
            GuidelineExtraction.created_at <= cutoff,
        )
    ).all()

    for job in stuck_jobs:
        job.status = "failed"
        job.step = "done"
        job.error_code = "INTERRUPTED"
        job.error_message = "Extraction was interrupted or timed out. Please try again."
        job.completed_at = datetime.now(timezone.utc)

    if stuck_jobs:
        db.commit()

    return len(stuck_jobs)


async def run_extraction_job(extraction_id: int, session_factory) -> None:
    """
    Background worker task that steps through:
    fetching -> cleaning -> extracting -> validating -> done.
    """
    client = get_llm_client()

    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if not job or job.status == "cancelled":
            return

        job.status = "running"
        job.step = "fetching" if job.source_type == "url" else "cleaning"
        db.commit()

    raw_content = ""
    is_html = True
    final_url = None
    warnings: list[dict[str, str]] = []

    # Step 1: Fetching (if URL)
    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if job.status == "cancelled":
            return

        if job.source_type == "url":
            job.step = "fetching"
            db.commit()
            try:
                fetch_res = await safe_fetch_url(job.source_url)
                raw_content = fetch_res.content
                final_url = fetch_res.final_url
                is_html = "html" in fetch_res.content_type
                if fetch_res.warnings:
                    warnings.extend(fetch_res.warnings)
            except FetchError as e:
                job.status = "failed"
                job.step = "done"
                job.error_code = e.code
                job.error_message = e.message
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
            except Exception as e:
                job.status = "failed"
                job.step = "done"
                job.error_code = "UNREACHABLE"
                job.error_message = f"Failed to fetch guideline URL: {e}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return
        else:
            raw_content = job.source_text or ""
            is_html = "<html" in raw_content.lower() or "<p>" in raw_content.lower()

    # Step 2: Cleaning
    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if job.status == "cancelled":
            return
        job.step = "cleaning"
        if final_url:
            job.final_url = final_url
        db.commit()

    try:
        cleaned_text, title, clean_warnings = clean_guideline_content(raw_content, is_html=is_html)
        if clean_warnings:
            warnings.extend(clean_warnings)
        _, lang_warnings = detect_guideline_language(cleaned_text)
        if lang_warnings:
            warnings.extend(lang_warnings)
    except CleanError as e:
        with session_factory() as db:
            job = db.get(GuidelineExtraction, extraction_id)
            job.status = "failed"
            job.step = "done"
            job.error_code = e.code
            job.error_message = e.message
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        return

    text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

    # Check cache before calling LLM
    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if job.status == "cancelled":
            return

        job.source_text = cleaned_text
        job.source_text_hash = text_hash
        
        cached_job = find_cached_extraction(db, job.user_id, text_hash, getattr(client, "model_name", "fake"))
        if cached_job and cached_job.draft:
            job.draft = cached_job.draft
            job.warnings = cached_job.warnings
            job.cached = True
            job.status = "completed"
            job.step = "done"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        db.commit()

    # Step 3: Chunking & Step 4: Extracting
    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if job.status == "cancelled":
            return
        job.step = "extracting"
        db.commit()

    chunks, chunk_warnings = build_text_chunks(cleaned_text)
    if chunk_warnings:
        warnings.extend(chunk_warnings)

    try:
        draft, extract_warnings, token_usage = await orchestrate_extraction(
            chunks, client, source_text=cleaned_text
        )
        if extract_warnings:
            warnings.extend(extract_warnings)
    except LLMError as e:
        with session_factory() as db:
            job = db.get(GuidelineExtraction, extraction_id)
            job.status = "failed"
            job.step = "done"
            job.error_code = e.code
            job.error_message = e.message
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        return
    except Exception as e:
        with session_factory() as db:
            job = db.get(GuidelineExtraction, extraction_id)
            job.status = "failed"
            job.step = "done"
            job.error_code = "INTERNAL"
            job.error_message = "An unexpected error occurred during extraction."
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        return

    # Step 5: Validating and saving draft
    with session_factory() as db:
        job = db.get(GuidelineExtraction, extraction_id)
        if job.status == "cancelled":
            return

        job.step = "validating"
        job.draft = draft
        job.warnings = warnings
        job.llm_model = getattr(client, "model_name", "gemini-2.5-flash")
        job.prompt_version = getattr(client, "prompt_version", "v1")
        job.input_tokens = token_usage.get("input_tokens", 0)
        job.output_tokens = token_usage.get("output_tokens", 0)
        job.status = "completed"
        job.step = "done"
        job.completed_at = datetime.now(timezone.utc)

        # Log activity if linked to a project
        if job.project_id:
            domain = ""
            if job.source_url:
                try:
                    domain = urlsplit(job.source_url).hostname or ""
                except Exception:
                    pass
            log_activity(
                db=db,
                user_id=job.user_id,
                project_id=job.project_id,
                event_type="guideline_extracted",
                details={"domain": domain} if domain else {},
            )

        db.commit()
