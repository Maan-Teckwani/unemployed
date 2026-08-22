"""API endpoints for Skill Gap Intelligence, Score Simulation, and Learning Roadmaps."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import embed_passage
from app.ai.roadmap import generate_roadmap
from app.ai.skill_analytics import analyze_market_skills, simulate_skill_acquisition
from app.db.models import KBChunk, SkillRoadmap
from app.db.session import get_db
from app.schemas import (
    RoadmapGenerateIn,
    RoadmapOut,
    RoadmapUpdateIn,
    SkillAnalyticsOut,
    SkillSimulateIn,
    SkillSimulateOut,
)

router = APIRouter(tags=["skills-and-roadmaps"])

STATUSES = ("in_progress", "completed", "archived")


@router.get("/skills/analytics", response_model=SkillAnalyticsOut)
def get_skill_analytics(
    role_family: str | None = None, db: Session = Depends(get_db)
) -> dict:
    """Compute aggregate market skill demand vs candidate mastery across all active jobs."""
    return analyze_market_skills(db, role_family)


@router.post("/skills/simulate", response_model=SkillSimulateOut)
def simulate_skills(
    payload: SkillSimulateIn, db: Session = Depends(get_db)
) -> dict:
    """Simulate acquiring target skills and calculate exact match score lift across jobs."""
    return simulate_skill_acquisition(payload.target_skills, db)


@router.get("/roadmaps", response_model=list[RoadmapOut])
def list_roadmaps(db: Session = Depends(get_db)) -> list[SkillRoadmap]:
    """List all saved learning roadmaps, newest first."""
    return list(
        db.scalars(select(SkillRoadmap).order_by(SkillRoadmap.created_at.desc()))
    )


@router.post("/roadmaps/generate", response_model=RoadmapOut, status_code=201)
def create_roadmap(
    payload: RoadmapGenerateIn, db: Session = Depends(get_db)
) -> SkillRoadmap:
    """Generate and persist a new multi-skill project learning roadmap."""
    chunks = list(db.scalars(select(KBChunk)))
    strengths = sorted({t for c in chunks for t in (c.technologies or [])})

    blueprint = generate_roadmap(
        target_skills=payload.target_skills,
        role_family=payload.role_family,
        estimated_weeks=payload.estimated_weeks,
        candidate_strengths=strengths,
    )

    roadmap = SkillRoadmap(**blueprint)
    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)
    return roadmap


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapOut)
def get_roadmap(roadmap_id: int, db: Session = Depends(get_db)) -> SkillRoadmap:
    """Get a single learning roadmap by ID."""
    roadmap = db.get(SkillRoadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="roadmap not found")
    return roadmap


@router.patch("/roadmaps/{roadmap_id}", response_model=RoadmapOut)
def update_roadmap(
    roadmap_id: int, payload: RoadmapUpdateIn, db: Session = Depends(get_db)
) -> SkillRoadmap:
    """Update milestone tasks/deliverables or roadmap status."""
    roadmap = db.get(SkillRoadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="roadmap not found")

    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(
                status_code=422, detail=f"status must be one of {STATUSES}"
            )
        roadmap.status = payload.status
    if payload.milestones is not None:
        roadmap.milestones = payload.milestones

    db.commit()
    db.refresh(roadmap)
    return roadmap


@router.post("/roadmaps/{roadmap_id}/complete-to-kb")
def complete_to_kb(roadmap_id: int, db: Session = Depends(get_db)) -> dict:
    """Convert a completed roadmap project into verified Knowledge Base chunks."""
    roadmap = db.get(SkillRoadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="roadmap not found")

    # The Knowledge Base is the evidence a resume is built from, so only a
    # project that was actually finished may enter it. Without this gate the
    # blueprint alone — a plan, not a thing you did — ends up on a resume.
    milestones = list(roadmap.milestones or [])
    unfinished = [m for m in milestones if not (isinstance(m, dict) and m.get("completed"))]
    if not milestones or unfinished:
        raise HTTPException(
            status_code=400,
            detail="finish every milestone before adding this project to your Knowledge Base",
        )

    roadmap.status = "completed"

    # Compose text for the main project chunk
    technologies = list(roadmap.target_skills or [])
    tech_str = ", ".join(technologies)
    bullet = (
        roadmap.resume_bullet_preview
        or f"Built {roadmap.title} leveraging {tech_str} to solve high-volume distributed challenges."
    )

    text_to_embed = f"{roadmap.title}. {bullet}. Technologies: {tech_str}"
    vector = embed_passage(text_to_embed)

    chunk = KBChunk(
        type="project",
        title=roadmap.title,
        context=f"Project Roadmap ({roadmap.role_family.title()})",
        company=None,
        date_range=None,
        accomplishment=bullet,
        technologies=technologies,
        skills=technologies,
        impact="Implemented end-to-end multi-skill project blueprint.",
        embedding=vector,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    return {
        "status": "ok",
        "message": f"Successfully created Knowledge Base chunk for '{roadmap.title}'.",
        "chunk_id": chunk.id,
    }


@router.delete("/roadmaps/{roadmap_id}", status_code=204)
def delete_roadmap(roadmap_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a roadmap blueprint."""
    roadmap = db.get(SkillRoadmap, roadmap_id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="roadmap not found")
    db.delete(roadmap)
    db.commit()
