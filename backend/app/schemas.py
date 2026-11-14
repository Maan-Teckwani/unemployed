"""Pydantic request/response models for the API boundary."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    profile_id: int | None = None


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
    profile_id: int | None = None


class ResumeProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_roles: list[str] = []
    description: str = ""


class ResumeProfileOut(ResumeProfileIn):
    id: int
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


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
    profile_id: int | None = None
    resume_id: int | None = None
    application_url: str = ""
    follow_up_at: datetime | None = None


class ApplicationAnswerIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1)
    category: str = Field(default="general", max_length=40)
    is_sensitive: bool = False
    explicit_approval: bool = False


class ApplicationAnswerOut(ApplicationAnswerIn):
    id: int
    use_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationAnswerUseIn(BaseModel):
    job_id: int | None = None


class ApplicationAnalyticsOut(BaseModel):
    total: int
    by_status: dict[str, int]
    sent: int
    response_count: int
    response_rate: float
    interview_count: int
    offer_count: int
    conversion_rate: float
    answer_uses: int


class AssistantStartIn(BaseModel):
    profile_id: int | None = None
    resume_id: int | None = None


class AssistantStateOut(BaseModel):
    session_id: str
    job_id: int
    state: str
    message: str
    safe_fields_filled: int = 0
    blocked_fields: list[str] = []
    application_url: str


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


class WorkflowSettingsIn(BaseModel):
    daily_application_goal: int = Field(default=3, ge=0, le=100)
    follow_up_days: int = Field(default=7, ge=1, le=90)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    week_starts_monday: bool = True

    def model_post_init(self, __context: object) -> None:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc


class WorkflowSettingsOut(WorkflowSettingsIn):
    id: int
    model_config = {"from_attributes": True}


class DeleteDataIn(BaseModel):
    confirmation: str


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


class InterviewPrepIn(BaseModel):
    profile_id: int | None = None


class CompanyIntelIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    title: str = Field(default="", max_length=300)
    content: str = Field(min_length=10)
    source_url: str = ""
    source_type: str = "user_note"


class InterviewQuestion(BaseModel):
    question: str
    answer: str
    source_chunk_ids: list[int] = []


class InterviewPrepOut(BaseModel):
    job_id: int
    profile_id: int | None
    questions: list[InterviewQuestion]
    talking_points: list[str]
    source_chunk_ids: list[int]
    generated_at: datetime

    model_config = {"from_attributes": True}


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


# ---- Skills & Roadmaps -------------------------------------------------------
class MarketSkillItem(BaseModel):
    skill: str
    frequency: int
    percentage: float
    is_mastered: bool
    category: str
    importance: float
    potential_score_lift: float
    sample_companies: list[str] = []


class DomainClusterItem(BaseModel):
    category: str
    mastered_count: int
    missing_count: int
    skills: list[MarketSkillItem] = []


class SkillAnalyticsOut(BaseModel):
    total_jobs_analyzed: int
    candidate_skills_count: int
    market_readiness_pct: float
    missing_skills_count: int = 0
    mastered_skills_count: int = 0
    top_missing_skills: list[MarketSkillItem] = []
    top_mastered_skills: list[MarketSkillItem] = []
    domain_clusters: list[DomainClusterItem] = []


class SkillSimulateIn(BaseModel):
    target_skills: list[str] = Field(min_length=1)


class ImpactedJobItem(BaseModel):
    job_id: int
    company: str
    title: str
    old_score: float
    new_score: float
    score_lift: float


class SkillSimulateOut(BaseModel):
    target_skills: list[str]
    previous_avg_score: float
    new_avg_score: float
    avg_lift: float
    unlocked_jobs_count: int
    impacted_jobs: list[ImpactedJobItem] = []


class RoadmapGenerateIn(BaseModel):
    target_skills: list[str] = Field(min_length=1)
    role_family: str = "backend"
    estimated_weeks: int = Field(default=3, ge=1, le=8)


class RoadmapMilestoneItem(BaseModel):
    week: int
    title: str
    objective: str
    tasks: list[str] = []
    deliverable: str = ""
    completed: bool = False


class EngineeringChallengeItem(BaseModel):
    challenge: str
    solution: str
    impact: str = ""


class RoadmapOut(BaseModel):
    id: int
    title: str
    summary: str
    role_family: str
    target_skills: list[str]
    status: str
    estimated_weeks: int
    architecture: str
    milestones: list[RoadmapMilestoneItem]
    engineering_challenges: list[EngineeringChallengeItem] = []
    resume_bullet_preview: str
    interview_talking_points: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoadmapUpdateIn(BaseModel):
    status: str | None = None
    milestones: list[dict] | None = None
