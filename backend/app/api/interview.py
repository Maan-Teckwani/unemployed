"""Interview preparation and grounded company intelligence endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import interview as generator
from app.ai.retrieve import retrieve
from app.db.models import (
    CompanyIntel,
    InterviewPrep,
    Job,
    JobRequirements,
    KBChunk,
)
from app.db.session import get_db
from app.schemas import CompanyIntelIn, InterviewPrepIn

router = APIRouter(tags=["interview-and-company-intelligence"])


def _requirements(row: JobRequirements | None) -> dict:
    return {
        "required_skills": list(row.required_skills or []) if row else [],
        "preferred_skills": list(row.preferred_skills or []) if row else [],
        "responsibilities": list(row.responsibilities or []) if row else [],
        "seniority": row.seniority if row else "",
        "min_years": row.min_years if row else 0,
    }


@router.get("/jobs/{job_id}/interview-prep")
def get_interview_prep(job_id: int, db: Session = Depends(get_db)) -> dict | None:
    row = db.get(InterviewPrep, job_id)
    if row is None:
        return None
    return {
        "job_id": row.job_id, "profile_id": row.profile_id,
        "questions": row.questions or [], "talking_points": row.talking_points or [],
        "source_chunk_ids": row.source_chunk_ids or [],
        "generated_at": row.generated_at,
    }


@router.post("/jobs/{job_id}/interview-prep", status_code=201)
def create_interview_prep(
    job_id: int, payload: InterviewPrepIn = InterviewPrepIn(),
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    evidence = retrieve(
        db, job.title, _requirements(db.get(JobRequirements, job_id)),
        k=12, profile_id=payload.profile_id,
    )
    if not evidence:
        raise HTTPException(status_code=400, detail="import verified experience first")
    evidence_data = [{
        "id": c.id, "title": c.title, "accomplishment": c.accomplishment,
        "technologies": list(c.technologies or []), "skills": list(c.skills or []),
    } for c in evidence]
    result = generator.generate(
        {"title": job.title, "company": job.company, "description": job.description},
        _requirements(db.get(JobRequirements, job_id)), evidence_data,
    )
    row = db.get(InterviewPrep, job_id)
    if row is None:
        row = InterviewPrep(job_id=job_id)
        db.add(row)
    row.profile_id = payload.profile_id
    row.questions = result["questions"]
    row.talking_points = result["talking_points"]
    row.source_chunk_ids = result["source_chunk_ids"]
    db.commit()
    db.refresh(row)
    return get_interview_prep(job_id, db)


@router.get("/company-intelligence/{company_name}")
def list_company_intelligence(company_name: str, db: Session = Depends(get_db)) -> dict:
    notes = list(db.scalars(
        select(CompanyIntel)
        .where(CompanyIntel.company_name.ilike(company_name))
        .order_by(CompanyIntel.created_at.desc())
    ))
    jobs = list(db.scalars(
        select(Job).where(Job.company.ilike(company_name)).order_by(Job.last_seen.desc())
    ))
    return {
        "company_name": company_name,
        "facts": [_intel_dict(n) for n in notes],
        "jobs": [{"id": j.id, "title": j.title, "location": j.location,
                  "description": j.description} for j in jobs[:20]],
    }


@router.post("/company-intelligence", status_code=201)
def add_company_intelligence(payload: CompanyIntelIn, db: Session = Depends(get_db)) -> dict:
    row = CompanyIntel(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _intel_dict(row)


@router.post("/company-intelligence/{company_name}/summarize")
def summarize_company_intelligence(company_name: str, db: Session = Depends(get_db)) -> dict:
    data = list_company_intelligence(company_name, db)
    if not data["facts"] and not data["jobs"]:
        raise HTTPException(status_code=404, detail="no stored company evidence")
    return generator.summarize_company(company_name, data["facts"], data["jobs"])


def _intel_dict(row: CompanyIntel) -> dict:
    return {"id": row.id, "company_name": row.company_name, "title": row.title,
            "content": row.content, "source_url": row.source_url,
            "source_type": row.source_type, "created_at": row.created_at}
