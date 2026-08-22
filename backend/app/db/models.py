"""ORM models: the candidate profile, knowledge-base chunks, and ingested jobs.

A KB chunk is ONE accomplishment with enough context to stand on its own. This
is the atomic unit we embed and later retrieve against a job description.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db.session import Base
from app.db.types import Embedding, JSONColumn, StringList
from app.ingestion.role_family import DEFAULT_FAMILIES


class CandidateProfile(Base):
    """The single owner of this knowledge base (one row)."""

    __tablename__ = "candidate_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    # e.g. {"github": "...", "linkedin": "...", "portfolio": "..."}
    links: Mapped[dict] = mapped_column(JSONColumn, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    # Free text, e.g. "B.Tech Computer Science, VIT Vellore, 2022-2026 | CGPA 8.6".
    # A fresher resume is incomplete without it, and it is never LLM-generated.
    education: Mapped[str] = mapped_column(Text, default="")
    # Just the institution name, e.g. "VIT Vellore". Stored separately because
    # alumni outreach searches on it, and parsing it back out of the free-text
    # education line would be guesswork.
    college: Mapped[str] = mapped_column(String(200), default="")


class KBChunk(Base):
    """One accomplishment + its context, plus its embedding vector."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # project | experience | leadership | achievement | skill | certification
    #   | education
    # Free text rather than an enum on purpose: adding a kind is a code change,
    # not a migration, and app/ai/parse.py owns the list that is accepted.
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    context: Mapped[str | None] = mapped_column(String(300), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date_range: Mapped[str | None] = mapped_column(String(100), nullable=True)

    accomplishment: Mapped[str] = mapped_column(Text)
    technologies: Mapped[list[str]] = mapped_column(StringList, default=list)
    skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding: Mapped[list[float]] = mapped_column(Embedding(settings.embedding_dim))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Preferences(Base):
    """What the candidate will actually apply to (one row).

    These are filter *thresholds as data*: tuning who gets shown is a settings
    change, not a code change. They also feed the `preference_fit` matching
    feature.
    """

    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Maximum years of experience a posting may ask for. A fresher is 0-1.
    max_years: Mapped[int] = mapped_column(Integer, default=1)
    # Extracted seniority levels that are acceptable.
    allowed_seniority: Mapped[list[str]] = mapped_column(
        StringList, default=lambda: ["intern", "entry"]
    )
    # Any of ingestion.role_family.FAMILIES.
    role_families: Mapped[list[str]] = mapped_column(
        StringList, default=lambda: list(DEFAULT_FAMILIES)
    )
    # Where you can actually work — a hard filter (see ingestion.relevance).
    # "global" disables geographic filtering entirely.
    region: Mapped[str] = mapped_column(String(20), default="india")

    # Soft preferences — these shape ranking (the preference_fit feature) rather
    # than filtering, because a great role in the "wrong" city is still worth seeing.
    preferred_locations: Mapped[list[str]] = mapped_column(StringList, default=list)
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=True)


class Company(Base):
    """A company whose public job board we read.

    Lives in the database rather than a config file so it can be searched for and
    added from the UI without a restart — `app.ingestion.discover` seeds it, and
    the settings page manages it from there.
    """

    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("source", "token", name="uq_companies_source_token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(40))  # greenhouse | lever | ashby | smartrecruiters
    token: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    # Jobs matching the user's region when the board was found — useful signal
    # for whether a company is worth keeping.
    matched_jobs: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Job(Base):
    """One job posting, normalized to a common schema across all sources.

    Identity is (source, external_id) — that is what makes re-running the
    ingestion idempotent. `fingerprint` catches the same role appearing on two
    different boards. `last_seen` drives expiry: a job the source stopped
    listing is marked expired rather than deleted, so history is preserved.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
        Index("ix_jobs_status_posted_at", "status", "posted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source: Mapped[str] = mapped_column(String(40))  # greenhouse | lever
    external_id: Mapped[str] = mapped_column(String(200))

    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(400))
    location: Mapped[str] = mapped_column(String(300), default="")
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    apply_url: Mapped[str] = mapped_column(String(1000), default="")

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | expired
    # sha256(title + description): lets us skip work when nothing actually changed.
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    # sha256(normalized company + title): cross-source duplicate detection.
    fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)


class JobRequirements(Base):
    """What a job actually asks for, extracted from its description by the LLM.

    `source_hash` is the job's content_hash at extraction time. If the posting
    text changes the hash changes and we re-extract; otherwise we never pay the
    ~25s LLM cost for this job again.
    """

    __tablename__ = "job_requirements"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    required_skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    responsibilities: Mapped[list[str]] = mapped_column(StringList, default=list)

    seniority: Mapped[str] = mapped_column(String(40), default="")  # intern|entry|mid|senior|lead
    min_years: Mapped[int] = mapped_column(Integer, default=0)

    # 0..1 — how much we trust this extraction. Low confidence must never
    # silently hard-filter a job; it flags it instead.
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class JobEmbedding(Base):
    """Vector for a job, in the SAME space as kb_chunks (same model)."""

    __tablename__ = "job_embeddings"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(Embedding(settings.embedding_dim))
    source_hash: Mapped[str] = mapped_column(String(64), default="")


class Match(Base):
    """An explainable fit score between the candidate KB and one job.

    Every number here is reproducible from `why` — no black box. Filtered jobs
    are kept with a reason rather than deleted, so "why did this disappear?" is
    always answerable.
    """

    __tablename__ = "matches"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    f_semantic: Mapped[float] = mapped_column(Float, default=0.0)
    f_keyword: Mapped[float] = mapped_column(Float, default=0.0)
    f_required_cov: Mapped[float] = mapped_column(Float, default=0.0)
    f_preferred_cov: Mapped[float] = mapped_column(Float, default=0.0)
    f_preference_fit: Mapped[float] = mapped_column(Float, default=0.0)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    hard_filtered: Mapped[bool] = mapped_column(Boolean, default=False)
    filter_reason: Mapped[str] = mapped_column(String(200), default="")
    # "estimated" = ranked without the LLM (semantic + keywords only);
    # "full" = requirements extracted, all four features scored.
    tier: Mapped[str] = mapped_column(String(20), default="estimated")

    # Per-feature breakdown that the UI renders as "why 82%?"
    why: Mapped[dict] = mapped_column(JSONColumn, default=dict)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Resume(Base):
    """A tailored resume generated for one job.

    `bullets` stores each bullet WITH the KB chunk ids it came from. That link is
    the product's honesty guarantee: any line on the page can be traced back to a
    verified accomplishment, and anything untraceable never gets written.
    """

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    headline: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    # [{section, title, context, date_range, text, source_chunk_ids: [int]}]
    bullets: Mapped[list] = mapped_column(JSONColumn, default=list)

    # {keyword_coverage, matched, missing, parse_ok, warnings[]}
    # For a LaTeX resume this instead holds {latex_sections: [...]}: which
    # sections were rewritten and which were kept because validation failed.
    ats_report: Mapped[dict] = mapped_column(JSONColumn, default=dict)
    pdf_path: Mapped[str] = mapped_column(String(500), default="")
    # The whole tailored document, when generated from the user's own template.
    # Empty for resumes rendered into our built-in PDF layout.
    latex: Mapped[str] = mapped_column(Text, default="")
    edited: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResumeTemplate(Base):
    """A LaTeX resume the user already has and likes.

    We tailor *their* document rather than replacing it: people have spent hours
    on an Overleaf template, and handing back a different-looking PDF is a
    downgrade however good the wording is.
    """

    __tablename__ = "resume_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Application(Base):
    """Where the candidate is in the funnel for one job.

    Separate from `jobs` because a job is source data that the pipeline owns and
    overwrites, while this is the user's own state and must never be clobbered by
    a re-ingest.
    """

    __tablename__ = "applications"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    # todo | resume_ready | applied | outreach_sent | closed
    status: Mapped[str] = mapped_column(String(30), default="todo", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # When this first became an application that was actually sent. Set once and
    # never moved, including when the job is later closed.
    #
    # `updated_at` cannot answer "when did I apply": marking a job closed six
    # weeks later moves it, and status alone cannot answer it either, because a
    # rejection changes the status but does not un-send the application. The
    # home page counts effort rather than outcomes, so its number must never go
    # down — which is exactly what a column that is written once gives you.
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class Contact(Base):
    """A person worth reaching out to about one job.

    The app never scrapes LinkedIn — that violates their terms and risks the
    user's account. Instead each row carries a targeted *search URL* the user
    opens themselves, plus a grounded draft message. The human does the looking
    and the connecting; the tool removes the tedium of composing the query and
    the opening note.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    # alumni | same_role | eng_leader | recruiter | founder
    category: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(120), default="")
    search_url: Mapped[str] = mapped_column(String(1000), default="")
    draft: Mapped[str] = mapped_column(Text, default="")

    # Filled in by the user once they have actually found someone.
    name: Mapped[str] = mapped_column(String(200), default="")
    profile_url: Mapped[str] = mapped_column(String(1000), default="")
    # todo | found | contacted | replied
    status: Mapped[str] = mapped_column(String(20), default="todo")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProjectIdea(Base):
    """A portfolio project tailored to one job, to attach when reaching out.

    Building something relevant to the company's actual product is the strongest
    signal a fresher can send — far stronger than another line on a resume. The
    idea has to be *specific* and *finishable*, so it is grounded in both the
    job's requirements and the gaps in the candidate's own knowledge base.
    """

    __tablename__ = "project_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(300), default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    what_to_build: Mapped[str] = mapped_column(Text, default="")
    why_it_impresses: Mapped[str] = mapped_column(Text, default="")
    tech_stack: Mapped[list[str]] = mapped_column(StringList, default=list)
    # Skills the job wants that the KB does not yet evidence — the point of the build.
    covers_gaps: Mapped[list[str]] = mapped_column(StringList, default=list)
    scope: Mapped[str] = mapped_column(String(120), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PipelineRun(Base):
    """One execution of a long-running pipeline step, started from the UI.

    Fetching and scoring take minutes to tens of minutes — far too long for an
    HTTP request — so the work happens in a background thread and the browser
    polls this row for progress.

    The row is also the lock: a `running` row means no new run may start. Without
    it, a second click would launch a second forty-minute job against the same
    database.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # discover | ingest | enrich | rescore
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)

    done: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(300), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionRun(Base):
    """Audit row per (run, source). One failing connector must not hide the rest."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    company: Mapped[str] = mapped_column(String(200), default="")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0)
    jobs_expired: Mapped[int] = mapped_column(Integer, default=0)

    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SkillRoadmap(Base):
    """A multi-skill project learning roadmap designed to cover candidate macro skill gaps.

    Unlike ProjectIdea (which is 1-to-1 for a specific job), this bridges the
    highest-leverage missing skills across the entire market into one high-signal,
    multi-week portfolio project.
    """

    __tablename__ = "skill_roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    role_family: Mapped[str] = mapped_column(String(40), default="backend")
    target_skills: Mapped[list[str]] = mapped_column(StringList, default=list)

    # in_progress | completed | archived
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    estimated_weeks: Mapped[int] = mapped_column(Integer, default=3)
    architecture: Mapped[str] = mapped_column(Text, default="")

    # [{week: int, title: str, objective: str, tasks: list[str], deliverable: str, completed: bool}]
    milestones: Mapped[list] = mapped_column(JSONColumn, default=list)

    # [{challenge: str, solution: str, impact: str}]
    engineering_challenges: Mapped[list] = mapped_column(JSONColumn, default=list)

    resume_bullet_preview: Mapped[str] = mapped_column(Text, default="")
    interview_talking_points: Mapped[list[str]] = mapped_column(StringList, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
