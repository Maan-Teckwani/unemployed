"""Filter settings: what the candidate will actually apply to.

Re-scoring is exposed here rather than run automatically on save, so the user
sees explicitly that changing a filter recomputes the list — and because it is
pure arithmetic over cached extractions, it finishes in seconds.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Preferences
from app.db.session import get_db
from app.ingestion.cities import cities_in, resolve
from app.ingestion.enrich import rescore_all
from app.schemas import CityOut, PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


def _get_or_create(db: Session) -> Preferences:
    prefs = db.scalar(select(Preferences).limit(1))
    if prefs is None:
        prefs = Preferences()
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def _canonical_locations(raw: list[str]) -> list[str]:
    """Store one spelling per place, keeping anything we do not recognise.

    Someone who types "bangalore" gets "Bengaluru" saved, so the field reads back
    as the name postings actually use and two people who meant the same city do
    not end up with two different preferences. Matching resolves aliases anyway,
    so this is about what the settings page shows, not about correctness.

    An unrecognised place is kept exactly as typed. Dropping it would silently
    delete the preference of anyone living somewhere the list does not carry.
    """
    seen: list[str] = []
    for item in raw:
        text = " ".join(str(item).split())
        if not text:
            continue
        city = resolve(text)
        value = city.label if city else text
        if value.lower() not in {s.lower() for s in seen}:
            seen.append(value)
    return seen


@router.get("", response_model=PreferencesOut)
def get_preferences(db: Session = Depends(get_db)) -> Preferences:
    return _get_or_create(db)


@router.put("", response_model=PreferencesOut)
def update_preferences(data: PreferencesIn, db: Session = Depends(get_db)) -> Preferences:
    prefs = _get_or_create(db)
    prefs.region = data.region
    prefs.max_years = data.max_years
    prefs.allowed_seniority = data.allowed_seniority
    prefs.role_families = data.role_families
    prefs.preferred_locations = _canonical_locations(data.preferred_locations)
    prefs.remote_ok = data.remote_ok
    db.commit()
    db.refresh(prefs)
    return prefs


@router.get("/cities", response_model=list[CityOut])
def list_cities(region: str = "") -> list[CityOut]:
    """The places the location field can offer, for one region or all of them.

    Served from the backend rather than duplicated as a list in the frontend,
    because the same list is what decides whether a posting is even ingested.
    A dropdown that offered a city ingestion had never heard of would look like
    it worked and rank nothing.
    """
    chosen = cities_in(region) if region else cities_in("global")
    return [
        CityOut(id=c.id, label=c.label, region=c.region, aliases=list(c.aliases))
        for c in chosen
    ]


@router.post("/rescore")
def rescore(db: Session = Depends(get_db)) -> dict:
    """Re-apply filters and recompute every score. No LLM calls."""
    return rescore_all(db)
