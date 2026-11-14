"""Personal workflow defaults (pacing, reminders, and calendar display)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WorkflowSettings
from app.db.session import get_db
from app.schemas import WorkflowSettingsIn, WorkflowSettingsOut

router = APIRouter(prefix="/workflow-settings", tags=["workflow"])


def _get_or_create(db: Session) -> WorkflowSettings:
    row = db.scalar(select(WorkflowSettings).limit(1))
    if row is None:
        row = WorkflowSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=WorkflowSettingsOut)
def get_workflow_settings(db: Session = Depends(get_db)) -> WorkflowSettings:
    return _get_or_create(db)


@router.put("", response_model=WorkflowSettingsOut)
def update_workflow_settings(
    data: WorkflowSettingsIn, db: Session = Depends(get_db)
) -> WorkflowSettings:
    row = _get_or_create(db)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row
