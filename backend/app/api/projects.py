from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models.journal import Journal
from app.db.models.project import Project
from app.db.models.project_journal import ProjectJournal
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.journal import JournalItemOut, MatchJournalItemOut
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate, ShortlistBody

router = APIRouter(prefix="/projects", tags=["projects"])


def get_user_project_or_404(
    project_id: int,
    user: User,
    db: Session,
) -> Project:
    project = db.execute(
        select(Project).where(
            Project.project_id == project_id,
            Project.user_id == user.user_id,
        )
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def get_journal_or_404(
    journal_id: int,
    db: Session,
) -> Journal:
    journal = db.execute(
        select(Journal).where(Journal.journal_id == journal_id)
    ).scalar_one_or_none()

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal not found",
        )
    return journal


def serialize_project(project: Project, db: Session) -> ProjectOut:
    selected_pj = db.execute(
        select(Journal)
        .join(ProjectJournal, ProjectJournal.journal_id == Journal.journal_id)
        .where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.is_selected.is_(True),
        )
    ).scalar_one_or_none()

    target_j_id = str(selected_pj.journal_id) if selected_pj else None
    target_j_title = selected_pj.journal_title if selected_pj else None

    abstract_clean = project.manuscript_abstract or ""
    word_count = len(abstract_clean.split()) if abstract_clean else 0

    return ProjectOut(
        id=str(project.project_id),
        title=project.project_title,
        abstract=abstract_clean,
        keywords=project.keywords or [],
        field="",
        target_journal_id=target_j_id,
        target_journal_title=target_j_title,
        status="Draft",
        updated_at=project.created_at.isoformat() if project.created_at else "",
        word_count=word_count,
        file_name=None,
        file_size=None,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOut:
    project = Project(
        user_id=current_user.user_id,
        project_title=data.title,
        manuscript_abstract=data.abstract or "",
        keywords=data.keywords or [],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project, db)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectOut]:
    projects = db.execute(
        select(Project)
        .where(Project.user_id == current_user.user_id)
        .order_by(Project.created_at.desc())
    ).scalars().all()

    return [serialize_project(p, db) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOut:
    project = get_user_project_or_404(project_id, current_user, db)
    return serialize_project(project, db)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectOut:
    project = get_user_project_or_404(project_id, current_user, db)

    if data.title is not None:
        project.project_title = data.title
    if data.abstract is not None:
        project.manuscript_abstract = data.abstract
    if data.keywords is not None:
        project.keywords = data.keywords

    db.commit()
    db.refresh(project)
    return serialize_project(project, db)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    project = get_user_project_or_404(project_id, current_user, db)
    db.delete(project)
    db.commit()
    return {"success": True, "id": str(project_id)}


# --- Shortlist Endpoints ---


@router.put("/{project_id}/shortlist/{journal_id}", response_model=MatchJournalItemOut)
def shortlist_journal(
    project_id: int,
    journal_id: int,
    body: Optional[ShortlistBody] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchJournalItemOut:
    project = get_user_project_or_404(project_id, current_user, db)
    journal = get_journal_or_404(journal_id, db)

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
    project = get_user_project_or_404(project_id, current_user, db)
    journal = get_journal_or_404(journal_id, db)

    pj = db.execute(
        select(ProjectJournal).where(
            ProjectJournal.project_id == project.project_id,
            ProjectJournal.journal_id == journal.journal_id,
        )
    ).scalar_one_or_none()

    if pj:
        if pj.is_selected:
            pj.is_shortlisted = False
        else:
            db.delete(pj)
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
    project = get_user_project_or_404(project_id, current_user, db)

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
