"""Deterministic quality checks for generated resumes."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Resume
from app.db.session import get_db

router = APIRouter(prefix="/resumes", tags=["resume quality"])


@router.get("/{resume_id}/quality")
def quality(resume_id: int, db: Session = Depends(get_db)) -> dict:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="resume not found")

    bullets = [b for b in (resume.bullets or []) if str(b.get("text", "")).strip()]
    texts = [str(b["text"]).strip().casefold() for b in bullets]
    duplicate_count = sum(count - 1 for count in Counter(texts).values() if count > 1)
    long_bullets = [
        b["text"] for b in bullets if len(str(b.get("text", "")).split()) > 30
    ]
    untraced = [
        b["text"]
        for b in bullets
        if not b.get("source_chunk_ids")
    ]
    sections = Counter(str(b.get("section", "Other")) for b in bullets)
    issues: list[str] = []
    if duplicate_count:
        issues.append(f"{duplicate_count} duplicate bullet(s)")
    if long_bullets:
        issues.append(f"{len(long_bullets)} bullet(s) exceed 30 words")
    if untraced:
        issues.append(f"{len(untraced)} bullet(s) lack evidence links")
    if not resume.skills:
        issues.append("Skills section is empty")
    if not bullets:
        issues.append("No resume bullets are present")

    score = max(0, 100 - 15 * len(issues))
    return {
        "resume_id": resume.id,
        "score": score,
        "issues": issues,
        "duplicate_count": duplicate_count,
        "long_bullets": long_bullets,
        "untraced_bullets": untraced,
        "sections": dict(sections),
        "ats_report": dict(resume.ats_report or {}),
    }
