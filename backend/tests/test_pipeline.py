"""The ingestion pipeline: reads every board at once, writes on one thread.

Three properties are worth more than speed here and all three are easy to lose
while chasing it: one dead board must not take the run down, the audit rows
must stay in a stable order, and a Session must never be touched from a thread
that does not own it.
"""
import threading
import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.connectors.base import RawJob
from app.connectors.registry import Company
from app.db.models import Base, IngestionRun, Job
from app.ingestion import pipeline


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _company(name, token=None):
    return Company(source="greenhouse", token=token or name.lower(), name=name)


def _job(company, external_id, title=None):
    # Distinct titles by default. Identity is (source, external_id), but there
    # is a second dedup on company+title that quietly drops the same role seen
    # on two boards, and a fixture that reuses one title tests that instead.
    return RawJob(
        source="greenhouse",
        external_id=external_id,
        company=company,
        title=title or f"Engineer {external_id}",
        location="Remote",
        remote=True,
        description="Build things with Python.",
        apply_url=f"https://example.com/{external_id}",
        posted_at=None,
    )


def _connector(jobs_by_token, delay=0.0, fails=()):
    """A stand-in board. Records which thread served each call."""
    threads = []

    def fetch(token, name, region):
        threads.append(threading.current_thread().name)
        if token in fails:
            raise RuntimeError(f"{token} is down")
        time.sleep(delay)
        return jobs_by_token.get(token, [])

    fetch.threads = threads
    return fetch


def _install(monkeypatch, fetch):
    monkeypatch.setitem(pipeline.CONNECTORS, "greenhouse", fetch)
    # Region filtering is exercised in test_relevance; here it would only hide
    # whether the pipeline itself stored what it was given.
    monkeypatch.setattr(pipeline, "is_relevant", lambda *a, **kw: True)


def test_every_company_is_stored(db, monkeypatch) -> None:
    fetch = _connector({"acme": [_job("Acme", "a1"), _job("Acme", "a2")], "globex": [_job("Globex", "g1")]})
    _install(monkeypatch, fetch)

    runs = pipeline.run_ingestion(db, [_company("Acme"), _company("Globex")])

    assert [r.company for r in runs] == ["Acme", "Globex"]
    assert [r.jobs_new for r in runs] == [2, 1]
    assert db.scalar(select(Job).where(Job.external_id == "a1")) is not None


def test_boards_are_read_at_the_same_time(db, monkeypatch) -> None:
    """Ninety six boards at two seconds each is three minutes of sitting still,
    and one slow board used to add its whole timeout to everyone else's wait."""
    fetch = _connector({}, delay=0.15)
    _install(monkeypatch, fetch)
    companies = [_company(f"C{i}") for i in range(8)]

    started = time.time()
    pipeline.run_ingestion(db, companies)
    took = time.time() - started

    assert took < 8 * 0.15 * 0.6, "boards were read one after another"
    assert len(set(fetch.threads)) > 1


def test_the_database_is_only_touched_from_the_calling_thread(db, monkeypatch) -> None:
    """A Session belongs to one thread. Fetching in a pool and writing from it
    is the kind of bug that works on a laptop and corrupts under load."""
    main = threading.current_thread().name
    fetch = _connector({"acme": [_job("Acme", "a1")]})
    _install(monkeypatch, fetch)
    seen = []
    original = pipeline._upsert
    monkeypatch.setattr(
        pipeline,
        "_upsert",
        lambda session, raw: (seen.append(threading.current_thread().name), original(session, raw))[1],
    )

    pipeline.run_ingestion(db, [_company("Acme")])

    assert seen == [main]
    assert main not in fetch.threads, "the fetch did not actually leave this thread"


def test_one_dead_board_does_not_take_the_run_down(db, monkeypatch) -> None:
    fetch = _connector({"globex": [_job("Globex", "g1")]}, fails={"acme"})
    _install(monkeypatch, fetch)

    runs = pipeline.run_ingestion(db, [_company("Acme"), _company("Globex")])

    assert [r.ok for r in runs] == [False, True]
    assert "is down" in runs[0].error
    assert runs[1].jobs_new == 1


def test_audit_rows_follow_the_companies_not_the_answers(db, monkeypatch) -> None:
    """Boards answer in whatever order they feel like. If the rows followed
    that, the same run would look different every night for no reason."""
    slow = {"acme": [_job("Acme", "a1")]}

    def fetch(token, name, region):
        time.sleep(0.2 if token == "acme" else 0.0)
        return slow.get(token, [])

    _install(monkeypatch, fetch)
    runs = pipeline.run_ingestion(db, [_company("Acme"), _company("Globex")])
    assert [r.company for r in runs] == ["Acme", "Globex"]


def test_a_company_is_one_transaction(db, monkeypatch) -> None:
    """It used to be one per job: a couple of thousand transactions per run
    against a file another thread is reading."""
    fetch = _connector({"acme": [_job("Acme", f"a{i}") for i in range(20)]})
    _install(monkeypatch, fetch)
    commits = []
    original = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(1), original())[1])

    pipeline.run_ingestion(db, [_company("Acme")])

    assert len(commits) == 1, f"{len(commits)} commits for one company"
    assert db.scalar(select(IngestionRun)).jobs_new == 20


def test_running_twice_changes_nothing(db, monkeypatch) -> None:
    """Identity is (source, external_id), so a second run updates rather than
    inserting. This is the property the whole daily loop rests on."""
    fetch = _connector({"acme": [_job("Acme", "a1"), _job("Acme", "a2")]})
    _install(monkeypatch, fetch)

    pipeline.run_ingestion(db, [_company("Acme")])
    runs = pipeline.run_ingestion(db, [_company("Acme")])

    assert runs[0].jobs_new == 0
    assert runs[0].jobs_updated == 2
    assert len(db.scalars(select(Job)).all()) == 2


def test_a_job_the_board_stopped_listing_expires(db, monkeypatch) -> None:
    _install(monkeypatch, _connector({"acme": [_job("Acme", "a1"), _job("Acme", "a2")]}))
    pipeline.run_ingestion(db, [_company("Acme")])

    _install(monkeypatch, _connector({"acme": [_job("Acme", "a1")]}))
    runs = pipeline.run_ingestion(db, [_company("Acme")])

    assert runs[0].jobs_expired == 1
    assert db.scalar(select(Job).where(Job.external_id == "a2")).status == "expired"


def test_a_failed_board_expires_nothing(db, monkeypatch) -> None:
    """Expiring on failure would mark a whole company gone because their web
    server had a bad minute."""
    _install(monkeypatch, _connector({"acme": [_job("Acme", "a1")]}))
    pipeline.run_ingestion(db, [_company("Acme")])

    _install(monkeypatch, _connector({}, fails={"acme"}))
    pipeline.run_ingestion(db, [_company("Acme")])

    assert db.scalar(select(Job).where(Job.external_id == "a1")).status == "active"


def test_the_same_role_from_two_boards_is_stored_once(db, monkeypatch) -> None:
    _install(
        monkeypatch,
        _connector(
            {
                "acme": [_job("Acme", "a1", title="Backend Engineer")],
                "acme2": [_job("Acme", "b1", title="Backend Engineer")],
            }
        ),
    )
    runs = pipeline.run_ingestion(db, [_company("Acme"), _company("Acme", token="acme2")])
    assert [r.jobs_new for r in runs] == [1, 0]
    assert len(db.scalars(select(Job)).all()) == 1


def test_counting_does_not_wait_for_a_flush(db, monkeypatch) -> None:
    """The counters are incremented before anything necessarily writes. Left to
    the column defaults they are None until SQLAlchemy happens to flush, and
    the tests above only passed because a lookup inside _upsert triggered one.
    The real run, where the first board returned nothing to look up, crashed."""
    _install(monkeypatch, _connector({}))  # no jobs, so nothing forces a flush
    runs = pipeline.run_ingestion(db, [_company("Acme")])
    assert (runs[0].jobs_new, runs[0].jobs_updated, runs[0].jobs_seen) == (0, 0, 0)


def test_no_companies_is_not_an_error(db, monkeypatch) -> None:
    """A fresh install has none, and a thread pool of zero workers raises."""
    assert pipeline.run_ingestion(db, []) == []


def test_progress_counts_boards_as_they_answer(db, monkeypatch) -> None:
    _install(monkeypatch, _connector({}))
    seen = []
    pipeline.run_ingestion(
        db, [_company(f"C{i}") for i in range(3)], on_progress=lambda d, t, m: seen.append((d, t))
    )
    assert seen[-1] == (3, 3)
    assert [d for d, _ in seen] == sorted(d for d, _ in seen), "progress went backwards"
