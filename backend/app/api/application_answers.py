"""A small, user-controlled library of reusable application answers."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationAnswer, ApplicationAnswerUse, Job
from app.db.session import get_db
from app.schemas import ApplicationAnswerIn, ApplicationAnswerOut, ApplicationAnswerUseIn

router = APIRouter(prefix="/application-answers", tags=["application answers"])

SENSITIVE_TERMS = (
    "gender", "race", "ethnicity", "disability", "veteran", "demographic",
    "religion", "sexual orientation", "pregnant", "citizenship", "visa",
)


def _is_sensitive(question: str, declared: bool) -> bool:
    lowered = question.casefold()
    return declared or any(term in lowered for term in SENSITIVE_TERMS)


def _validate_approval(data: ApplicationAnswerIn) -> bool:
    sensitive = _is_sensitive(data.question, data.is_sensitive)
    if sensitive and not data.explicit_approval:
        raise HTTPException(
            status_code=400,
            detail="Sensitive answers require explicit approval before saving.",
        )
    return sensitive


@router.get("", response_model=list[ApplicationAnswerOut])
def list_answers(db: Session = Depends(get_db)) -> list[ApplicationAnswer]:
    return list(db.scalars(select(ApplicationAnswer).order_by(ApplicationAnswer.updated_at.desc())))


@router.post("", response_model=ApplicationAnswerOut, status_code=201)
def create_answer(data: ApplicationAnswerIn, db: Session = Depends(get_db)) -> ApplicationAnswer:
    sensitive = _validate_approval(data)
    values = data.model_dump()
    values["is_sensitive"] = sensitive
    row = ApplicationAnswer(**values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{answer_id}", response_model=ApplicationAnswerOut)
def update_answer(
    answer_id: int, data: ApplicationAnswerIn, db: Session = Depends(get_db)
) -> ApplicationAnswer:
    row = db.get(ApplicationAnswer, answer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="answer not found")
    sensitive = _validate_approval(data)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.is_sensitive = sensitive
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{answer_id}", status_code=204)
def delete_answer(answer_id: int, db: Session = Depends(get_db)) -> None:
    row = db.get(ApplicationAnswer, answer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="answer not found")
    db.delete(row)
    db.commit()


@router.post("/{answer_id}/use", response_model=ApplicationAnswerOut)
def use_answer(
    answer_id: int, data: ApplicationAnswerUseIn, db: Session = Depends(get_db)
) -> ApplicationAnswer:
    row = db.get(ApplicationAnswer, answer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="answer not found")
    if row.is_sensitive and not row.explicit_approval:
        raise HTTPException(status_code=400, detail="Sensitive answer is not approved.")
    if data.job_id is not None and db.get(Job, data.job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    db.add(ApplicationAnswerUse(answer_id=answer_id, job_id=data.job_id))
    row.use_count += 1
    db.commit()
    db.refresh(row)
    return row
