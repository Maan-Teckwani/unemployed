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


@pytest.mark.parametrize("ending", ["closed", "rejected"])
def test_a_rejection_does_not_un_send_the_application(db, ending) -> None:
    """The whole reason this column exists. Neither being turned down nor giving
    up on a job may shrink the pile — the application was still sent."""
    set_status(db, "applied")
    stamped = db.get(Application, 1).applied_at

    set_status(db, ending)

    assert db.get(Application, 1).applied_at == stamped


@pytest.mark.parametrize("status", ["test", "interview", "offer", "rejected"])
def test_you_cannot_reach_the_funnel_without_having_applied(db, status) -> None:
    """Going straight to "interview" on a job never marked applied still means
    an application went out, so it earns its sheet and its date."""
    set_status(db, status)
    assert db.get(Application, 1).applied_at is not None


def test_moving_along_the_funnel_keeps_the_original_date(db) -> None:
    """The sheet changes colour as you progress; it does not become a new one."""
    set_status(db, "applied")
    first = db.get(Application, 1).applied_at

    for status in ("test", "interview", "offer"):
        set_status(db, status)
        assert db.get(Application, 1).applied_at == first

    assert applications.stats(db=db)["pile"] == 1, "one job is one application"


def test_closing_a_job_you_never_sent_stamps_nothing(db) -> None:
    """Deciding against a job is not an application. The pile counts what left."""
    set_status(db, "closed")

    assert db.get(Application, 1).applied_at is None
    assert applications.stats(db=db)["pile"] == 0


@pytest.mark.parametrize("undo", ["todo", "resume_ready"])
def test_marking_a_job_applied_by_mistake_can_be_taken_back(db, undo) -> None:
    """The one thing that removes a sheet from the pile.

    Everything else about this column is "written once", so that a rejection
    cannot shrink the pile. But a wrong selection has to be undoable, and moving
    a job back to a not-sent status is the user saying they have not applied
    after all — a correction, not an outcome.
    """
    set_status(db, "applied")
    assert db.get(Application, 1).applied_at is not None

    set_status(db, undo)

    assert db.get(Application, 1).applied_at is None
    assert applications.stats(db=db)["pile"] == 0


def test_applying_again_after_taking_it_back_is_a_fresh_date(db) -> None:
    set_status(db, "applied")
    set_status(db, "todo")
    set_status(db, "applied")

    assert db.get(Application, 1).applied_at is not None
    assert applications.stats(db=db)["pile"] == 1, "still one job, one sheet"


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


def test_a_prepared_resume_is_not_an_application(db) -> None:
    """Generated resumes expire minutes after they are made, so "resume ready"
    cannot mean there is a resume waiting — only that nothing has been sent."""
    set_status(db, "resume_ready")

    assert db.get(Application, 1).applied_at is None
    assert setup.status(db=db)["counts"]["pile"] == 0


def test_every_funnel_status_is_accepted(db) -> None:
    """The picker offers these, so the API has to take them."""
    for status in applications.STATUSES:
        set_status(db, status)
        assert db.get(Application, 1).status == status
