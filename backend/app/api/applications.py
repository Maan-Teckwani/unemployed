"""Application status: the user's own progress through the funnel.

Deliberately dumb storage. The value is that yesterday's decisions survive today's
re-ingest, so the daily list is "what's left to do" rather than the same 25 jobs
every morning.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Application, Job
from app.db.session import get_db
from app.schemas import ApplicationIn

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


@router.put("/{job_id}")
def set_status(job_id: int, data: ApplicationIn, db: Session = Depends(get_db)) -> dict:
    if data.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES}")
    if db.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    app_row = db.get(Application, job_id) or Application(job_id=job_id)
    app_row.status = data.status
    app_row.notes = data.notes
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
    db.commit()
    db.refresh(app_row)
    return {
        "job_id": app_row.job_id,
        "status": app_row.status,
        "notes": app_row.notes,
        "updated_at": _iso(app_row.updated_at),
        "applied_at": _iso(app_row.applied_at),
    }
