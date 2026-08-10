"""The pile on the home page counts effort, so its number must never fall.

Everything here is really one property under different pressures: `applied_at`
is written the first time an application goes out and is never written again.
Status can move anywhere afterwards — closed, back to todo, applied a second
time — and the record of having sent it survives all of it.

The route functions are called directly against an in-memory database rather
than through TestClient, because constructing the app runs the lifespan in
app.main, which releases stale runs against the *real* configured database and
starts a background sweeper thread. A unit test should not do either.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import applications, setup
from app.db.models import Application, Job
from app.db.session import Base
from app.schemas import ApplicationIn


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        session.add(
            Job(id=1, source="greenhouse", external_id="x1", company="Acme", title="SDE I")
        )
        session.commit()
        yield session


def set_status(db, status: str, job_id: int = 1) -> dict:
    return applications.set_status(job_id, ApplicationIn(status=status), db=db)


def test_a_job_you_have_not_sent_has_no_date(db) -> None:
    set_status(db, "todo")
    assert db.get(Application, 1).applied_at is None


def test_applying_stamps_it(db) -> None:
    set_status(db, "applied")
    assert db.get(Application, 1).applied_at is not None


def test_outreach_alone_also_counts_as_sent(db) -> None:
    """Reaching out without submitting a form is still an application sent, and
    a job that goes straight there would otherwise be a card with no date."""
    set_status(db, "outreach_sent")
    assert db.get(Application, 1).applied_at is not None


def test_a_rejection_does_not_un_send_the_application(db) -> None:
    """The whole reason this column exists. Closing a job must not shrink the pile."""
    set_status(db, "applied")
    stamped = db.get(Application, 1).applied_at

    set_status(db, "closed")

    assert db.get(Application, 1).applied_at == stamped


def test_applying_twice_is_still_one_application(db) -> None:
    set_status(db, "applied")
    first = db.get(Application, 1).applied_at

    set_status(db, "todo")
    set_status(db, "applied")

    assert db.get(Application, 1).applied_at == first


def test_both_responses_carry_the_date(db) -> None:
    """The UI buckets "today" itself, so the date has to survive the wire."""
    written = set_status(db, "applied")
    assert written["applied_at"].startswith(str(db.get(Application, 1).applied_at.year))

    listed = applications.list_applications(db=db)[0]
    assert listed["applied_at"] == written["applied_at"]
    assert listed["title"] == "SDE I"


def test_an_unsent_application_serialises_a_null_rather_than_being_absent(db) -> None:
    set_status(db, "resume_ready")
    assert applications.list_applications(db=db)[0]["applied_at"] is None


def test_the_pile_counts_closed_jobs_too(db) -> None:
    db.add(Job(id=2, source="lever", external_id="x2", company="Beta", title="SDE II"))
    db.commit()
    set_status(db, "applied", job_id=1)
    set_status(db, "applied", job_id=2)
    set_status(db, "closed", job_id=2)

    assert applications.stats(db=db)["pile"] == 2
    assert applications.stats(db=db)["applied"] == 1, "status still describes where it is now"
    assert setup.status(db=db)["counts"]["pile"] == 2


def test_setup_counts_resumes_waiting_to_be_sent(db) -> None:
    """These are the outlined cards on the pile — work done, not yet sent."""
    set_status(db, "resume_ready")

    counts = setup.status(db=db)["counts"]
    assert counts["resume_ready"] == 1
    assert counts["pile"] == 0
