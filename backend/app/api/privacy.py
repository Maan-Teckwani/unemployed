"""Local-only data export and deletion controls.

The export is deliberately assembled on the server and returned as a download;
it never calls a remote service. Connector tokens and vector columns are not
part of a backup, so a backup cannot become a credential leak.
"""
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.db.models import (
    Application, ApplicationAnswer, ApplicationAnswerUse, ApplicationStatusEvent,
    CandidateProfile, Company, CompanyIntel, Contact, IngestionRun, InterviewPrep,
    Job, JobEmbedding, JobRequirements, KBChunk, Match, PipelineRun, Preferences,
    ProjectIdea, Resume, ResumeProfile, ResumeTemplate, SkillRoadmap, WorkflowSettings,
)
from app.db.session import get_db
from app.schemas import DeleteDataIn

router = APIRouter(prefix="/privacy", tags=["privacy"])
_EXCLUDED = {"embedding", "token", "pdf_path"}


def _value(value: object) -> object:
    if isinstance(value, datetime):
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()
    return value


def _rows(db: Session, model: type) -> list[dict]:
    names = [c.key for c in inspect(model).columns if c.key not in _EXCLUDED]
    return [{name: _value(getattr(row, name)) for name in names}
            for row in db.scalars(select(model)).all()]


@router.get("/export")
def export_data(db: Session = Depends(get_db)) -> Response:
    """Download a JSON backup to the browser; no data is sent elsewhere."""
    models = {
        "candidate_profile": CandidateProfile,
        "resume_profiles": ResumeProfile,
        "kb_chunks": KBChunk,
        "preferences": Preferences,
        "workflow_settings": WorkflowSettings,
        "companies": Company,
        "jobs": Job,
        "job_requirements": JobRequirements,
        "matches": Match,
        "resumes": Resume,
        "resume_templates": ResumeTemplate,
        "applications": Application,
        "application_answers": ApplicationAnswer,
        "application_answer_uses": ApplicationAnswerUse,
        "application_status_events": ApplicationStatusEvent,
        "contacts": Contact,
        "project_ideas": ProjectIdea,
        "interview_prep": InterviewPrep,
        "company_intel": CompanyIntel,
        "pipeline_runs": PipelineRun,
        "ingestion_runs": IngestionRun,
        "skill_roadmaps": SkillRoadmap,
    }
    payload = {
        "format": "job-search-local-backup",
        "version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "data": {name: _rows(db, model) for name, model in models.items()},
    }
    return Response(
        content=json.dumps(payload, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="job-search-backup.json"'},
    )


@router.delete("/data")
def delete_data(data: DeleteDataIn, db: Session = Depends(get_db)) -> dict:
    """Permanently remove all locally stored data after an explicit confirmation."""
    if data.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail='confirmation must be exactly "DELETE"')

    # Delete dependants first for databases where foreign keys are enforced.
    ordered = [
        ApplicationAnswerUse, ApplicationStatusEvent, ApplicationAnswer,
        InterviewPrep, Application, Contact, ProjectIdea, Match, JobRequirements, JobEmbedding,
        CompanyIntel,
        Resume, ResumeTemplate, KBChunk, ResumeProfile, WorkflowSettings,
        Preferences, CandidateProfile, Company, Job, PipelineRun, IngestionRun,
        SkillRoadmap,
    ]
    counts = {}
    for model in ordered:
        counts[model.__tablename__] = db.query(model).delete(synchronize_session=False)
    db.commit()

    # PDFs are generated artifacts, not database rows. Only remove the app's
    # own generated directory, never an arbitrary path stored in a row.
    generated = REPO_ROOT / "generated"
    if generated.is_dir():
        for path in generated.glob("resume_*.pdf"):
            path.unlink(missing_ok=True)
    return {"deleted": counts}


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@router.get("/calendar.ics")
def export_calendar(db: Session = Depends(get_db)) -> Response:
    """Export application follow-ups as a local iCalendar file."""
    settings = db.scalar(select(WorkflowSettings).limit(1))
    timezone = ZoneInfo(settings.timezone if settings else "UTC")
    rows = db.execute(
        select(Application, Job).join(Job, Application.job_id == Job.id)
        .where(Application.follow_up_at.is_not(None))
        .order_by(Application.follow_up_at)
    ).all()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Local Job Search//Follow-ups//EN"]
    for application, job in rows:
        when = application.follow_up_at
        if when is None:
            continue
        aware = (when.replace(tzinfo=UTC) if when.tzinfo is None else when).astimezone(timezone)
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:application-{application.job_id}@local-job-search",
            f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID={settings.timezone if settings else 'UTC'}:{aware.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{_ics_escape(f'Follow up: {job.title} at {job.company}')}",
            f"DESCRIPTION:{_ics_escape(f'Status: {application.status}')}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="application-follow-ups.ics"'},
    )
