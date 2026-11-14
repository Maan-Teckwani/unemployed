"""Job endpoints: browse what the ingestion pipeline collected.

Read-only for now. Sprint 3 adds extracted requirements and match scores; this
view exists so ingestion problems are visible immediately instead of silently
poisoning everything downstream.
"""
import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Job, Match
from app.db.session import get_db
from app.ingestion.enrich import enrich_one
from app.schemas import IngestionRunOut, JobDetailOut, JobOut, ManualJobIn

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    q: str | None = None,
    company: str | None = None,
    status: str = "active",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[Job]:
    """List ingested jobs, newest posting first."""
    stmt = select(Job).where(Job.status == status)
    if company:
        stmt = stmt.where(Job.company == company)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Job.title.ilike(pattern), Job.description.ilike(pattern)))
    stmt = stmt.order_by(Job.posted_at.desc().nullslast()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.post("/manual", status_code=201)
def create_manual_job(data: ManualJobIn, db: Session = Depends(get_db)) -> dict:
    """Add a job the user found elsewhere, then extract + score it immediately.

    Same pipeline as ingested jobs, so a pasted JD gets the identical explainable
    score and can drive resume generation. Runs the local LLM inline (~30s).
    """
    external_id = hashlib.sha256(
        f"{data.company}|{data.title}|{data.description[:500]}".encode()
    ).hexdigest()[:32]

    job = db.scalar(
        select(Job).where(Job.source == "manual", Job.external_id == external_id)
    )
    if job is None:
        job = Job(
            source="manual",
            external_id=external_id,
            company=data.company.strip(),
            title=data.title.strip(),
            location=data.location.strip(),
            remote="remote" in f"{data.location} {data.title}".lower(),
            description=data.description.strip(),
            apply_url=data.apply_url.strip(),
            posted_at=datetime.now(UTC),
            content_hash=hashlib.sha256(
                f"{data.title}\n{data.description}".encode()
            ).hexdigest(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    result = enrich_one(db, job)
    return {"job_id": job.id, "score": result["score"], "filtered": result["hard_filtered"]}


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    """Counts for the dashboard header."""
    by_status = dict(
        db.execute(select(Job.status, func.count()).group_by(Job.status)).all()
    )
    companies = db.scalar(select(func.count(func.distinct(Job.company)))) or 0
    return {
        "active": by_status.get("active", 0),
        "expired": by_status.get("expired", 0),
        "companies": companies,
    }


@router.get("/alerts")
def alerts(
    since_hours: int = 24,
    min_score: float = 0.65,
    limit: int = 25,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return newly ingested, rankable jobs worth an explicit user review."""
    since_hours = max(1, min(since_hours, 24 * 30))
    stmt = (
        select(Job, Match)
        .join(Match, Match.job_id == Job.id)
        .where(
            Job.status == "active",
            Job.first_seen >= datetime.now(UTC) - timedelta(hours=since_hours),
            Match.hard_filtered.is_(False),
            Match.score >= min_score,
        )
        .order_by(Match.score.desc(), Job.first_seen.desc())
        .limit(max(1, min(limit, 100)))
    )
    return [
        {
            "job": JobOut.model_validate(job).model_dump(),
            "score": match.score,
            "why": match.why,
        }
        for job, match in db.execute(stmt).all()
    ]


@router.get("/runs", response_model=list[IngestionRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[IngestionRun]:
    """Most recent ingestion runs — the first place to look when jobs go missing."""
    stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    return list(db.scalars(stmt))


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
