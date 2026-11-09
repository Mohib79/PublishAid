import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.project import Project
from app.db.session import SessionLocal
from app.services.activity import log_activity
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


def run_cleanup_sweep(db: Session, now: datetime | None = None) -> int:
    """
    1. Purges expired files older than WORKSPACE_FILE_TTL_MINUTES using SELECT ... FOR UPDATE SKIP LOCKED.
    2. Sweeps orphan files and folders on disk older than the TTL.
    Returns the number of purged project files.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    ttl_minutes = settings.WORKSPACE_FILE_TTL_MINUTES
    cutoff = now - timedelta(minutes=ttl_minutes)

    storage = StorageService(settings.STORAGE_ROOT)
    purged_count = 0

    # 1. Database-driven purge
    try:
        expired_projects = db.execute(
            select(Project)
            .where(
                Project.manuscript_uploaded_at.is_not(None),
                Project.manuscript_uploaded_at <= cutoff,
                Project.current_file_path.is_not(None),
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()

        for project in expired_projects:
            try:
                old_path = project.current_file_path
                storage.delete_manuscript_file(old_path)
                project.current_file_path = None
                project.file_deleted_at = now

                # Log activity without bumping project updated_at
                log_activity(db, project.user_id, project, "manuscript_purged")
                db.commit()
                purged_count += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to purge expired file for project #{project.project_id}: {e}")

    except Exception as e:
        logger.error(f"Error querying expired projects: {e}")

    # 2. Orphan disk sweep
    try:
        storage_root = Path(settings.STORAGE_ROOT).resolve()
        if storage_root.is_dir():
            for pdir in storage_root.iterdir():
                if pdir.is_dir():
                    try:
                        dir_name = pdir.name
                        if dir_name.isdigit():
                            pid = int(dir_name)
                            # Check if project exists
                            proj_exists = db.execute(
                                select(Project.project_id).where(Project.project_id == pid)
                            ).scalar_one_or_none()

                            if not proj_exists:
                                # Folder exists for deleted project
                                import shutil
                                shutil.rmtree(pdir, ignore_errors=True)
                            else:
                                # Sweep unreferenced files in active project dir older than TTL
                                referenced_key = db.execute(
                                    select(Project.current_file_path).where(Project.project_id == pid)
                                ).scalar_one_or_none()

                                for f in pdir.iterdir():
                                    if f.is_file():
                                        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                                        if mtime <= cutoff:
                                            rel_key = f"{pid}/{f.name}"
                                            if rel_key != referenced_key:
                                                f.unlink(missing_ok=True)
                    except Exception as ex:
                        logger.warning(f"Error sweeping directory {pdir.name}: {ex}")

    except Exception as e:
        logger.error(f"Error during orphan sweep: {e}")

    return purged_count


class BackgroundCleanupRunner:
    def __init__(self, interval_seconds: int = 600):
        self.interval = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        # Run once immediately at startup
        try:
            with SessionLocal() as db:
                run_cleanup_sweep(db)
        except Exception as e:
            logger.error(f"Startup cleanup sweep failed: {e}")

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.interval):
                break
            try:
                with SessionLocal() as db:
                    run_cleanup_sweep(db)
            except Exception as e:
                logger.error(f"Periodic cleanup sweep failed: {e}")
