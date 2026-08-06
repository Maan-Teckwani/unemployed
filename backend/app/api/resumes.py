"""Resume endpoints: generate a tailored resume for a job, then download it.

Generation is on demand, never batch: it costs LLM time and, more importantly,
every resume is meant to be reviewed by a human before it is sent anywhere.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import ats, pdf
from app.ai.generate_resume import generate
from app.ai.latex import tailor
from app.ai.retrieve import retrieve_all
from app.db.models import CandidateProfile, Job, JobRequirements, Resume, ResumeTemplate
from app.db.retention import purge_expired_resumes
from app.db.session import get_db
from app.schemas import ResumeEditIn

router = APIRouter(prefix="/resumes", tags=["resumes"])

GENERATED_DIR = Path(__file__).resolve().parents[2] / "generated"


@router.post("/generate/{job_id}")
def generate_resume(job_id: int, format: str = "pdf", db: Session = Depends(get_db)) -> dict:
    """Retrieve -> generate -> validate -> render. Returns the stored resume.

    `format=latex` tailors the user's own template instead of rendering ours.
    """
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    profile = db.scalar(select(CandidateProfile))
    if profile is None or not profile.name:
        raise HTTPException(
            status_code=400,
            detail="Add your profile (name, email) before generating a resume.",
        )

    requirements = _requirements_for(db, job_id)
    # The whole knowledge base, most relevant first: the model should choose the
    # best evidence from everything the candidate has done, not from a top-8 slice.
    chunks = retrieve_all(db, job.title, requirements)
    if not chunks:
        raise HTTPException(
            status_code=400, detail="Knowledge base is empty — import your experience first."
        )

    if format == "latex":
        return _generate_latex(db, job, requirements, chunks)

    result = generate(profile, job, requirements, chunks)
    if not result["bullets"]:
        raise HTTPException(
            status_code=422,
            detail="No bullet survived truthfulness validation. Try again or enrich your KB.",
        )

    report = ats.keyword_coverage(result, requirements)
    resume = Resume(
        job_id=job_id,
        headline=job.title,
        summary=result["summary"],
        skills=result["skills"],
        bullets=result["bullets"],
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    pdf_path = GENERATED_DIR / f"resume_{resume.id}.pdf"
    pdf.render(profile, result, pdf_path)
    report.update(ats.check_pdf(pdf_path.read_bytes(), profile, result))
    report["rejected_bullets"] = result["rejected"]

    resume.pdf_path = str(pdf_path)
    resume.ats_report = report
    db.commit()
    db.refresh(resume)
    return _as_dict(resume, db)


def _generate_latex(db: Session, job: Job, requirements: dict, chunks: list) -> dict:
    """Fill the default template's sections for this job and store the document.

    No PDF: the document *is* the output, and the user compiles it in Overleaf
    where their template already lives. What each section did is recorded in
    `ats_report` so the UI can say "kept unchanged" rather than leaving the user
    to diff it themselves.

    Bullets are stored for the sections whose entries were chosen from the
    knowledge base rather than reworded. They carry the same
    `source_chunk_ids` the PDF path uses, so `_as_dict` resolves them into the
    accomplishment each one came from and the UI can prove the claim. A section
    that was only reworded has no bullets to attribute: its sentences started
    life in the user's own document.
    """
    template = db.scalar(
        select(ResumeTemplate).where(ResumeTemplate.is_default.is_(True))
    )
    if template is None:
        raise HTTPException(
            status_code=400, detail="Add a LaTeX template first (Templates page)."
        )

    document, sections = tailor(template.source, chunks, requirements)
    # A section that failed validation is kept as written, and the report says so.
    # That is a worse resume than a tailored one and a much better outcome than a
    # confident-sounding rewrite naming an employer the candidate never worked for.
    resume = Resume(
        job_id=job.id,
        headline=job.title,
        latex=document,
        bullets=_chosen_bullets(sections),
        ats_report={"latex_sections": sections},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return _as_dict(resume, db)


def _chosen_bullets(sections: list[dict]) -> list[dict]:
    """Flatten the per-section report into the bullet shape the UI already reads.

    Same keys as the PDF path produces, so `_as_dict` and the editor need no
    idea which renderer wrote them.
    """
    return [
        {
            "text": text,
            "source_chunk_ids": [chunk_id],
            "section": section["name"],
            "title": entry["title"],
        }
        for section in sections
        for entry in section.get("entries", [])
        for text, chunk_id in zip(entry["bullets"], entry["chunk_ids"])
    ]


@router.get("/{resume_id}/latex")
def download_latex(resume_id: int, db: Session = Depends(get_db)) -> Response:
    # Purge before reading, so an expired document can never be served even if
    # the sweeper has not come round to it yet.
    purge_expired_resumes(db)
    resume = db.get(Resume, resume_id)
    if resume is None or not resume.latex:
        raise HTTPException(status_code=404, detail="no latex for this resume")
    return Response(
        content=resume.latex,
        media_type="application/x-tex",
        headers={"Content-Disposition": f'attachment; filename="resume_{resume_id}.tex"'},
    )


@router.put("/{resume_id}")
def edit_resume(resume_id: int, data: ResumeEditIn, db: Session = Depends(get_db)) -> dict:
    """Save user edits, then re-render the PDF and re-run the ATS checks.

    The local model writes serviceable but sometimes clumsy prose; you know what
    reads well. Edits keep each bullet's source_chunk_ids, so a hand-written
    bullet is still traceable, and the PDF template is regenerated by us — the
    user edits words, never layout.
    """
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="resume not found")

    profile = db.scalar(select(CandidateProfile))
    kept = [b for b in data.bullets if str(b.get("text", "")).strip()]

    resume.summary = data.summary
    resume.skills = data.skills
    resume.bullets = kept
    resume.edited = True

    content = {"summary": resume.summary, "skills": resume.skills, "bullets": kept}
    pdf_path = GENERATED_DIR / f"resume_{resume.id}.pdf"
    pdf.render(profile, content, pdf_path)

    report = ats.keyword_coverage(content, _requirements_for(db, resume.job_id))
    report.update(ats.check_pdf(pdf_path.read_bytes(), profile, content))
    # Rejections belong to the generation that produced them, not to a manual edit.
    report["rejected_bullets"] = []

    resume.pdf_path = str(pdf_path)
    resume.ats_report = report
    db.commit()
    db.refresh(resume)
    return _as_dict(resume, db)


@router.get("/for-job/{job_id}")
def latest_for_job(job_id: int, db: Session = Depends(get_db)) -> dict | None:
    """Most recent *unexpired* resume generated for this job, if any."""
    purge_expired_resumes(db)
    resume = db.scalar(
        select(Resume).where(Resume.job_id == job_id).order_by(Resume.created_at.desc())
    )
    return _as_dict(resume, db) if resume else None


@router.get("/{resume_id}/pdf")
def download_pdf(resume_id: int, db: Session = Depends(get_db)) -> FileResponse:
    purge_expired_resumes(db)
    resume = db.get(Resume, resume_id)
    if resume is None or not resume.pdf_path or not Path(resume.pdf_path).exists():
        raise HTTPException(status_code=404, detail="pdf not found")
    return FileResponse(
        resume.pdf_path, media_type="application/pdf", filename=f"resume_{resume_id}.pdf"
    )


def _requirements_for(db: Session, job_id: int) -> dict:
    """Extracted requirements for a job, or empty ones if it was never enriched."""
    row = db.get(JobRequirements, job_id)
    if row is None:
        return {"required_skills": [], "preferred_skills": [], "responsibilities": []}
    return {
        "required_skills": list(row.required_skills or []),
        "preferred_skills": list(row.preferred_skills or []),
        "responsibilities": list(row.responsibilities or []),
    }


def _as_dict(resume: Resume, db: Session) -> dict:
    """Attach the source accomplishment text so the UI can prove each bullet."""
    from app.db.models import KBChunk

    ids = {i for b in resume.bullets for i in b.get("source_chunk_ids", [])}
    sources = {
        c.id: {"title": c.title, "accomplishment": c.accomplishment}
        for c in db.scalars(select(KBChunk).where(KBChunk.id.in_(ids)))
    } if ids else {}

    return {
        "id": resume.id,
        "job_id": resume.job_id,
        "headline": resume.headline,
        "summary": resume.summary,
        "skills": list(resume.skills or []),
        "bullets": list(resume.bullets or []),
        "latex": resume.latex or "",
        "ats_report": dict(resume.ats_report or {}),
        "sources": sources,
        "created_at": resume.created_at.isoformat(),
    }
