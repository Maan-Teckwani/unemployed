"""Pydantic request/response models for the API boundary."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.ingestion.role_family import DEFAULT_FAMILIES


# ---- Knowledge base ----------------------------------------------------------
class AccomplishmentIn(BaseModel):
    """One achievement. Becomes exactly one KB chunk."""

    text: str = Field(min_length=3)
    technologies: list[str] = []
    skills: list[str] = []
    impact: str | None = None


class KBItemIn(BaseModel):
    """A project/experience/etc. Its accomplishments are split into chunks."""

    type: str
    title: str
    context: str | None = None
    company: str | None = None
    date_range: str | None = None
    accomplishments: list[AccomplishmentIn] = Field(min_length=1)


class KBChunkOut(BaseModel):
    id: int
    type: str
    title: str
    context: str | None
    company: str | None
    date_range: str | None
    accomplishment: str
    technologies: list[str]
    skills: list[str]
    impact: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchResult(KBChunkOut):
    similarity: float


class ChunkIn(BaseModel):
    """A single chunk — the shape of a parsed proposal AND a reviewed save."""

    type: str = "experience"
    title: str
    context: str | None = None
    company: str | None = None
    date_range: str | None = None
    accomplishment: str = Field(min_length=1)
    technologies: list[str] = []
    skills: list[str] = []
    impact: str | None = None


# ---- Jobs --------------------------------------------------------------------
class JobOut(BaseModel):
    id: int
    source: str
    company: str
    title: str
    location: str
    remote: bool
    apply_url: str
    posted_at: datetime | None
    status: str

    model_config = {"from_attributes": True}


class JobDetailOut(JobOut):
    description: str
    first_seen: datetime
    last_seen: datetime


class MatchOut(BaseModel):
    """A ranked job plus the full reasoning behind its score."""

    job: JobOut
    status: str = "todo"
    tier: str = "estimated"
    score: float
    f_semantic: float
    f_keyword: float
    f_required_cov: float
    f_preferred_cov: float
    f_preference_fit: float = 0.0
    confidence: float
    hard_filtered: bool
    filter_reason: str
    why: dict

    model_config = {"from_attributes": True}


class IngestionRunOut(BaseModel):
    id: int
    source: str
    company: str
    started_at: datetime
    finished_at: datetime | None
    jobs_seen: int
    jobs_new: int
    jobs_updated: int
    jobs_expired: int
    ok: bool
    error: str | None

    model_config = {"from_attributes": True}


# ---- Resumes / applications --------------------------------------------------
class ResumeEditIn(BaseModel):
    """User-edited resume content.

    Only text the user can legitimately change: bullet wording, skills, summary.
    Bullets keep their source_chunk_ids so provenance survives an edit, and layout
    stays code-owned so editing can never break ATS parseability.
    """

    summary: str = ""
    skills: list[str] = []
    bullets: list[dict] = []


class ResumeTemplateIn(BaseModel):
    """The user's own LaTeX resume, pasted from Overleaf."""

    name: str = Field(default="", max_length=200)
    source: str = Field(min_length=20)


class ApplicationIn(BaseModel):
    status: str = "todo"
    notes: str = ""


class ManualJobIn(BaseModel):
    """A job the user found themselves and pasted in."""

    title: str = Field(min_length=2)
    company: str = Field(min_length=1)
    description: str = Field(min_length=50)
    location: str = ""
    apply_url: str = ""


# ---- Preferences -------------------------------------------------------------
class PreferencesIn(BaseModel):
    # Hard filter: where you can actually work. "global" disables it.
    region: str = "india"
    max_years: int = Field(default=1, ge=0, le=10)
    allowed_seniority: list[str] = ["intern", "entry"]
    role_families: list[str] = list(DEFAULT_FAMILIES)
    # Soft: these shape ranking via preference_fit, they do not filter.
    preferred_locations: list[str] = []
    remote_ok: bool = True


class PreferencesOut(PreferencesIn):
    id: int
    model_config = {"from_attributes": True}


class CityOut(BaseModel):
    """One place the settings dropdown can offer."""

    id: str
    label: str
    region: str
    # Shown as "also written Bangalore", so someone looking for the name they
    # know can find the entry that is actually stored.
    aliases: list[str] = []


# ---- Pipeline ----------------------------------------------------------------
class PipelineRunIn(BaseModel):
    kind: str


# ---- Companies ---------------------------------------------------------------
class CompanyIn(BaseModel):
    source: str
    token: str
    name: str = ""
    matched_jobs: int = 0


# ---- Profile -----------------------------------------------------------------
class ProfileIn(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: dict[str, str] = {}
    summary: str = ""
    education: str = ""
    college: str = ""


# ---- Outreach ----------------------------------------------------------------
class ContactUpdateIn(BaseModel):
    name: str = ""
    profile_url: str = ""
    status: str = "todo"
    notes: str = ""
    draft: str = ""


class ProfileOut(ProfileIn):
    id: int
    model_config = {"from_attributes": True}
