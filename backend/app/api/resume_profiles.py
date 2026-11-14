"""Role-specific resume profiles over the shared knowledge base."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ResumeProfile
from app.db.session import get_db
from app.schemas import ResumeProfileIn, ResumeProfileOut

router = APIRouter(prefix="/resume-profiles", tags=["resume-profiles"])


def _ensure_default(db: Session) -> ResumeProfile:
    profile = db.scalar(select(ResumeProfile).order_by(ResumeProfile.id))
    if profile is None:
        profile = ResumeProfile(name="General", is_default=True)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=list[ResumeProfileOut])
def list_profiles(db: Session = Depends(get_db)) -> list[ResumeProfile]:
    _ensure_default(db)
    return list(db.scalars(select(ResumeProfile).order_by(ResumeProfile.id)))


@router.post("", response_model=ResumeProfileOut, status_code=201)
def create_profile(
    data: ResumeProfileIn, db: Session = Depends(get_db)
) -> ResumeProfile:
    profile = ResumeProfile(
        name=data.name.strip(),
        target_roles=data.target_roles,
        description=data.description,
        is_default=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/{profile_id}/default", response_model=ResumeProfileOut)
def set_default(profile_id: int, db: Session = Depends(get_db)) -> ResumeProfile:
    profile = db.get(ResumeProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="resume profile not found")
    for row in db.scalars(select(ResumeProfile)):
        row.is_default = row.id == profile_id
    db.commit()
    db.refresh(profile)
    return profile
