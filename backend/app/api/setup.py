"""Is this instance ready to use, and if not, what's the next step?

A first-time user needs to be told what to do in order — a profile with no
knowledge base produces nothing, and scoring before fetching produces nothing.
This endpoint answers that in one call so the home page can show a checklist
rather than leaving someone to guess.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    CandidateProfile,
    Company,
    Job,
    KBChunk,
    Match,
    Preferences,
)
from app.db.session import get_db

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    profile = db.scalar(select(CandidateProfile))
    kb_chunks = db.scalar(select(func.count()).select_from(KBChunk)) or 0
    companies = db.scalar(select(func.count()).select_from(Company)) or 0
    active_jobs = (
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "active")) or 0
    )
    scored = db.scalar(select(func.count()).select_from(Match)) or 0
    rankable = (
        db.scalar(
            select(func.count())
            .select_from(Match)
            .join(Job, Match.job_id == Job.id)
            .where(Match.hard_filtered.is_(False), Job.status == "active")
        )
        or 0
    )
    applied = (
        db.scalar(
            select(func.count()).select_from(Application).where(Application.status == "applied")
        )
        or 0
    )
    # The number the pile on the home page is drawn from. It lives here, on a
    # call the nav already makes after every navigation, so showing the count on
    # every page costs no extra request.
    pile = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.applied_at.is_not(None))
        )
        or 0
    )

    # A profile needs a name to head a resume; preferences exist once saved.
    steps = [
        {
            "id": "profile",
            "label": "Add your profile",
            "done": bool(profile and profile.name.strip()),
            "href": "/profile",
        },
        {
            "id": "knowledge_base",
            "label": "Import your experience",
            "done": kb_chunks > 0,
            "href": "/kb/import",
            "detail": f"{kb_chunks} accomplishment{'' if kb_chunks == 1 else 's'}",
        },
        {
            "id": "filters",
            "label": "Set your filters",
            "done": db.scalar(select(Preferences)) is not None,
            "href": "/settings",
        },
        {
            "id": "jobs",
            "label": "Fetch and score jobs",
            "done": active_jobs > 0 and scored > 0,
            "action": "ingest",
            "detail": f"{active_jobs} active from {companies} companies"
            + (f" · {rankable} worth applying to" if scored else ""),
        },
    ]

    return {
        "steps": steps,
        "ready": all(s["done"] for s in steps),
        "counts": {
            "kb_chunks": kb_chunks,
            "companies": companies,
            "active_jobs": active_jobs,
            "scored": scored,
            "rankable": rankable,
            "applied": applied,
            "pile": pile,
        },
    }
