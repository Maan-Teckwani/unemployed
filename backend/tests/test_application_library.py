import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import application_answers, applications
from app.db.models import Application, Job
from app.db.session import Base
from app.schemas import ApplicationAnswerIn, ApplicationAnswerUseIn, ApplicationIn


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        session.add(Job(id=1, source="greenhouse", external_id="x", company="Acme", title="Engineer"))
        session.commit()
        yield session


def test_sensitive_answers_require_explicit_approval(db):
    with pytest.raises(HTTPException, match="explicit approval"):
        application_answers.create_answer(
            ApplicationAnswerIn(question="Are you a veteran?", answer="No"), db=db
        )

    answer = application_answers.create_answer(
        ApplicationAnswerIn(
            question="Are you a veteran?", answer="No", explicit_approval=True
        ),
        db=db,
    )
    assert answer.is_sensitive is True
    application_answers.use_answer(answer.id, ApplicationAnswerUseIn(job_id=1), db=db)
    assert answer.use_count == 1


def test_analytics_reports_funnel_rates_and_answer_uses(db):
    for status in ("applied", "interview", "offer"):
        applications.set_status(1, ApplicationIn(status=status), db=db)
    answer = application_answers.create_answer(
        ApplicationAnswerIn(question="Why this role?", answer="I build useful systems."),
        db=db,
    )
    application_answers.use_answer(answer.id, ApplicationAnswerUseIn(job_id=1), db=db)

    result = applications.analytics(db=db)
    assert result["sent"] == 1
    assert result["interview_count"] == 1
    assert result["offer_count"] == 1
    assert result["response_rate"] == 1.0
    assert result["answer_uses"] == 1
    assert db.get(Application, 1).status == "offer"
