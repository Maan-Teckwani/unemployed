"""Run the long pipeline steps from the browser.

Fetching jobs takes minutes and scoring takes tens of minutes, so neither can
happen inside an HTTP request. Each starts a background thread that owns its own
database session and writes progress to a `pipeline_runs` row; the browser polls
that row.

**Only one run at a time.** The `running` row is the lock — without it a second
click would start a second forty-minute job against the same tables. The check
and the insert happen in one transaction so two near-simultaneous clicks cannot
both win.
"""
import logging
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.companies import SEED_COMPANIES
from app.db.models import Company, PipelineRun, Preferences
from app.db.session import SessionLocal, get_db
from app.ingestion.discover import discover
from app.ingestion.enrich import enrich, rescore_all
from app.ingestion.pipeline import run_ingestion
from app.ingestion.relevance import DEFAULT_REGION
from app.schemas import PipelineRunIn

log = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

KINDS = ("discover", "ingest", "rescore")

LABELS = {
    "discover": "Finding company job boards",
    "ingest": "Fetching and scoring jobs",
    "rescore": "Re-scoring",
}

# How many jobs get the slow LLM read after a fetch. Every job is still filtered
# and cheaply ranked; this is only the depth of the expensive second pass. Apply
# today never needs more than this, and it keeps a fetch to about ten minutes
# instead of forty — scoring is not a thing the user should have to decide to do.
SCORE_DEPTH = 25


def release_stale_runs() -> None:
    """A run only ever lives in a thread of this process, so any row still marked
    `running` at startup belongs to a process that is gone — a Ctrl-C or a
    container restart mid-fetch. Left alone it holds the lock forever and every
    run button stays dead with no way out but SQL.
    """
    with SessionLocal() as db:
        for run in db.scalars(select(PipelineRun).where(PipelineRun.status == "running")):
            run.status, run.message = "failed", "Interrupted"
            run.error = "The server restarted while this was running."
            run.finished_at = datetime.now(UTC)
        db.commit()


@router.post("/run", status_code=202)
def start_run(data: PipelineRunIn, db: Session = Depends(get_db)) -> dict:
    if data.kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {KINDS}")

    active = db.scalar(select(PipelineRun).where(PipelineRun.status == "running"))
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"{LABELS.get(active.kind, active.kind)} is already running",
        )

    run = PipelineRun(kind=data.kind, message=LABELS[data.kind], total=0)
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(target=_execute, args=(run.id, data.kind), daemon=True)
    thread.start()
    return _as_dict(run)


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict | None:
    """The current run, or the most recent finished one."""
    run = db.scalar(select(PipelineRun).order_by(PipelineRun.started_at.desc()))
    return _as_dict(run) if run else None


def ingest_and_score(db: Session, progress) -> None:
    """Fetch, then score, as one action.

    Jobs nobody has scored are jobs nobody can act on, so leaving the second half
    as its own button only created a state where the app looked broken and the
    fix was a forty-minute click the user had to know to make.
    """
    run_ingestion(db, on_progress=progress)
    enrich(db, top=SCORE_DEPTH, on_progress=progress)


def _execute(run_id: int, kind: str) -> None:
    """Runs in a background thread, so it needs its own session."""
    with SessionLocal() as db:
        run = db.get(PipelineRun, run_id)

        def progress(done: int, total: int, message: str) -> None:
            run.done, run.total, run.message = done, total, message
            db.commit()

        try:
            if kind == "ingest":
                ingest_and_score(db, progress)
            elif kind == "rescore":
                progress(0, 1, "Re-applying filters")
                rescore_all(db)
            else:
                _discover(db, progress)

            run.status, run.message = "done", "Finished"
        except BaseException as e:  # noqa: BLE001 - see below
            # BaseException, not Exception. This row is the lock, so a step that
            # dies without writing a terminal status here disables every run
            # button until someone restarts the server. `SystemExit` already did
            # exactly that once, and a thread swallows it without even a
            # traceback — so the handler cannot be selective about what it
            # survives. It records the reason and lets the thread end.
            log.exception("pipeline run %s (%s) failed", run_id, kind)
            # The step may have died mid-transaction; without this the commit
            # below would raise too, and the lock would be stuck all the same.
            db.rollback()
            run.status, run.error = "failed", str(e)[:2000] or e.__class__.__name__
            run.message = "Failed"
        finally:
            run.finished_at = datetime.now(UTC)
            db.commit()


def _discover(db: Session, progress) -> None:
    """Probe seed companies we do not already track."""
    preferences = db.scalar(select(Preferences))
    region = getattr(preferences, "region", None) or DEFAULT_REGION
    known = {c.name for c in db.scalars(select(Company))}
    names = [n for n in SEED_COMPANIES if n not in known]

    progress(0, len(names), f"Checking {len(names)} companies")
    found = discover(names, region, on_progress=progress)

    existing = {(c.source, c.token) for c in db.scalars(select(Company))}
    for entry in found:
        if (entry["source"], entry["token"]) in existing:
            continue
        db.add(
            Company(
                source=entry["source"],
                token=entry["token"],
                name=entry["name"],
                matched_jobs=entry["matched_jobs"],
            )
        )
        existing.add((entry["source"], entry["token"]))
    db.commit()
    # Both numbers, because "added 8" on its own reads as a poor result when it
    # is eight companies out of three hundred that have no public board to find.
    progress(
        len(names),
        len(names),
        f"Added {len(found)} of {len(names)} checked — the rest have no public board we can read",
    )


def _as_dict(run: PipelineRun) -> dict:
    return {
        "id": run.id,
        "kind": run.kind,
        "status": run.status,
        "done": run.done,
        "total": run.total,
        "message": run.message,
        "error": run.error,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
