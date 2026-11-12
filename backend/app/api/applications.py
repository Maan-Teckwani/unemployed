"""Application status: the user's own progress through the funnel.

Deliberately dumb storage. The value is that yesterday's decisions survive today's
re-ingest, so the daily list is "what's left to do" rather than the same 25 jobs
every morning.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Application, ApplicationAnswerUse, ApplicationStatusEvent, CandidateProfile, Job,
    Resume, ResumeProfile, WorkflowSettings,
)
from app.db.session import get_db
from app.schemas import ApplicationAnalyticsOut, ApplicationIn, AssistantStartIn, AssistantStateOut
from app.assistant.browser import assistant
from app.api.privacy import export_calendar

router = APIRouter(prefix="/applications", tags=["applications"])

# The funnel, in order. Everything from "applied" onward is a place an
# application can actually be once it has left your hands, which is what the
# pile on the home page draws.
STATUSES = (
    "todo",
    "resume_ready",
    "applied",
    "outreach_sent",
    "test",
    "interview",
    "offer",
    "rejected",
    "closed",
)

# The statuses that mean "this went out".
#
# All of them, not just "applied": you cannot be interviewing for a job you did
# not apply to, and a job that went straight to outreach without a form
# submission is still work done. `closed` is the one exception — it also covers
# deciding against a job you never sent anything for, so it stamps nothing on
# its own and simply keeps whatever date the row already had.
SENT = ("applied", "outreach_sent", "test", "interview", "offer", "rejected")

# The statuses that mean "this has not gone out". Moving *back* to one of these
# is the user saying they have not applied after all — a mis-click being undone,
# not an outcome — so it clears the date and the pile loses the sheet.
#
# This is the one thing that can shrink the pile, and it has to exist: without
# it a single wrong selection is permanent. Note what is *not* here: `closed`
# and `rejected` both leave the date alone, because being turned down or giving
# up does not un-send an application you really did send.
NOT_SENT = ("todo", "resume_ready")


def _iso(value: datetime | None) -> str | None:
    """ISO-8601 with an explicit offset, which `.isoformat()` alone cannot give.

    These columns are declared `DateTime(timezone=True)` and written with
    `datetime.now(UTC)`, but SQLite has no timezone type — the dialect formats
    the components into a string and drops the tzinfo, so what comes back out is
    a *naive* datetime whose clock is UTC. Serialised bare, that is
    "2026-08-13T19:32:47", and `new Date()` in the browser reads a timestamp
    with no offset as local time.

    Which broke the daily counter, and only for part of each day: an application
    sent at 00:05 in Delhi is stamped 18:35 UTC, the browser reads that as 18:35
    *yesterday*, and "today" stays at zero while the pile — which counts sheets
    of any date — goes up. Negative offsets fail the same way after their
    evening. Naive is taken as UTC because that is the only thing ever written.
    """
    if value is None:
        return None
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


@router.get("")
def list_applications(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Application, Job).join(Job, Application.job_id == Job.id)
    ).all()
    return [
        {
            "job_id": a.job_id,
            "status": a.status,
            "notes": a.notes,
            "updated_at": _iso(a.updated_at),
            "applied_at": _iso(a.applied_at),
            "title": j.title,
            "company": j.company,
            "profile_id": a.profile_id,
            "resume_id": a.resume_id,
            "application_url": a.application_url or j.apply_url,
            "follow_up_at": _iso(a.follow_up_at),
            "assistant_state": a.assistant_state,
        }
        for a, j in rows
    ]


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    counts = dict(
        db.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
    )
    result = {status: counts.get(status, 0) for status in STATUSES}
    # Everything ever sent, including the jobs that have since been closed. This
    # is deliberately not the sum of the "applied" and "outreach_sent" counts
    # above: those describe where a job is now, and this describes what you did.
    result["pile"] = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.applied_at.is_not(None))
        )
        or 0
    )
    return result


@router.get("/analytics", response_model=ApplicationAnalyticsOut)
def analytics(db: Session = Depends(get_db)) -> dict:
    counts = dict(
        db.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
    )
    sent = db.scalar(
        select(func.count()).select_from(Application).where(Application.applied_at.is_not(None))
    ) or 0
    response_count = sum(counts.get(status, 0) for status in ("test", "interview", "offer", "rejected"))
    interview_count = counts.get("interview", 0) + counts.get("offer", 0)
    offers = counts.get("offer", 0)
    answer_uses = db.scalar(select(func.count()).select_from(ApplicationAnswerUse)) or 0
    return {
        "total": sum(counts.values()),
        "by_status": {status: counts.get(status, 0) for status in STATUSES},
        "sent": sent,
        "response_count": response_count,
        "response_rate": round(response_count / sent, 4) if sent else 0.0,
        "interview_count": interview_count,
        "offer_count": offers,
        "conversion_rate": round(offers / sent, 4) if sent else 0.0,
        "answer_uses": answer_uses,
    }


@router.put("/{job_id}")
def set_status(job_id: int, data: ApplicationIn, db: Session = Depends(get_db)) -> dict:
    if data.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES}")
    if db.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    existing = db.get(Application, job_id)
    previous_status = existing.status if existing else None
    app_row = existing or Application(job_id=job_id)
    app_row.status = data.status
    app_row.notes = data.notes
    if "profile_id" in data.model_fields_set:
        app_row.profile_id = data.profile_id
    if "resume_id" in data.model_fields_set:
        app_row.resume_id = data.resume_id
    if "application_url" in data.model_fields_set and data.application_url:
        app_row.application_url = data.application_url
    if "follow_up_at" in data.model_fields_set:
        app_row.follow_up_at = data.follow_up_at
    # Stamped on the way in and not moved again while the job is out there:
    # closing it does not make it fewer than one application, and progressing
    # through test and interview does not make it more than one.
    if data.status in SENT and app_row.applied_at is None:
        app_row.applied_at = datetime.now(UTC)
    # Taking it back to "not sent" is the exception, and the only thing that can
    # remove a sheet from the pile. Marking a job applied by mistake has to be
    # undoable, and "todo" is how someone says it.
    elif data.status in NOT_SENT:
        app_row.applied_at = None
    db.add(app_row)
    if previous_status != data.status:
        db.add(ApplicationStatusEvent(job_id=job_id, status=data.status))
    db.commit()
    db.refresh(app_row)
    return {
        "job_id": app_row.job_id,
        "status": app_row.status,
        "notes": app_row.notes,
        "updated_at": _iso(app_row.updated_at),
        "applied_at": _iso(app_row.applied_at),
        "follow_up_at": _iso(app_row.follow_up_at),
    }


@router.post("/{job_id}/assistant/start", response_model=AssistantStateOut)
def start_assistant(
    job_id: int, data: AssistantStartIn, db: Session = Depends(get_db)
) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    candidate = db.scalar(select(CandidateProfile))
    if candidate is None or not candidate.name:
        raise HTTPException(status_code=400, detail="complete your profile first")
    resume = db.get(Resume, data.resume_id) if data.resume_id else None
    if data.resume_id and resume is None:
        raise HTTPException(status_code=404, detail="resume not found")
    profile = db.get(ResumeProfile, data.profile_id) if data.profile_id else None
    if data.profile_id and profile is None:
        raise HTTPException(status_code=404, detail="resume profile not found")

    session = assistant.start(
        job_id=job_id,
        url=job.apply_url,
        candidate=candidate,
        resume_path=resume.pdf_path if resume else "",
    )
    row = db.get(Application, job_id) or Application(job_id=job_id)
    row.profile_id = profile.id if profile else None
    row.resume_id = resume.id if resume else None
    row.application_url = job.apply_url
    row.assistant_state = session["state"]
    db.add(row)
    db.commit()
    return session


@router.post("/assistant/{session_id}/prepare", response_model=AssistantStateOut)
def prepare_assistant(session_id: str, db: Session = Depends(get_db)) -> dict:
    session = assistant.prepare(session_id)
    row = db.get(Application, session["job_id"])
    if row:
        row.assistant_state = session["state"]
        db.commit()
    return session


@router.post("/assistant/{session_id}/submit", response_model=AssistantStateOut)
def submit_assistant(session_id: str, db: Session = Depends(get_db)) -> dict:
    session = assistant.submit(session_id)
    row = db.get(Application, session["job_id"])
    if row:
        row.status = "applied"
        row.applied_at = datetime.now(UTC)
        row.assistant_state = session["state"]
        db.add(ApplicationStatusEvent(job_id=row.job_id, status="applied"))
        if row.follow_up_at is None:
            settings = db.scalar(select(WorkflowSettings).limit(1))
            days = settings.follow_up_days if settings else 7
            row.follow_up_at = datetime.now(UTC) + timedelta(days=days)
        db.commit()
    return session


@router.get("/follow-ups")
def follow_ups(db: Session = Depends(get_db)) -> list[dict]:
    now = datetime.now(UTC)
    rows = db.execute(
        select(Application, Job)
        .join(Job, Application.job_id == Job.id)
        .where(
            Application.follow_up_at.is_not(None),
            Application.follow_up_at <= now,
            Application.status.not_in(("rejected", "closed", "offer")),
        )
        .order_by(Application.follow_up_at)
    ).all()
    return [
        {
            "job_id": app_row.job_id,
            "title": job.title,
            "company": job.company,
            "status": app_row.status,
            "follow_up_at": _iso(app_row.follow_up_at),
        }
        for app_row, job in rows
    ]


@router.get("/follow-ups.ics")
def follow_ups_calendar(db: Session = Depends(get_db)):
    """Download follow-up reminders for a calendar app without leaving the machine."""
    return export_calendar(db)
