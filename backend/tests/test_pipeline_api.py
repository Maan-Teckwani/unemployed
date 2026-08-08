"""The progress callback is optional by design — the CLIs pass nothing and must
keep working, while the UI passes a callback to drive its progress bar."""
import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import pipeline
from app.api.pipeline import KINDS, LABELS
from app.db.models import PipelineRun
from app.db.session import Base
from app.ingestion.enrich import enrich
from app.ingestion.pipeline import run_ingestion


@pytest.fixture
def sessions():
    """A real (in-memory) database, because what is worth testing here is the row
    a crashed run leaves behind — a fake session would assert nothing about it."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_progress_callback_is_optional_on_both_entry_points() -> None:
    """A required callback would have broken every existing CLI invocation."""
    for func in (run_ingestion, enrich):
        param = inspect.signature(func).parameters["on_progress"]
        assert param.default is None


def test_every_kind_has_a_human_label() -> None:
    """The 409 message names the running step, so a missing label would leak an id."""
    assert set(KINDS) == set(LABELS)
    assert all(LABELS[kind] for kind in KINDS)


def test_scoring_is_not_something_the_user_can_choose_to_skip() -> None:
    """Fetching without scoring leaves an app where nothing is rankable and
    nothing looks broken, so "enrich" is no longer a kind you can ask for."""
    assert "enrich" not in KINDS
    assert "ingest" in KINDS


def test_a_fetch_scores_what_it_fetched(monkeypatch) -> None:
    """Order matters: scoring before fetching would score yesterday's jobs."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        pipeline, "run_ingestion", lambda db, on_progress=None: calls.append(("fetch",))
    )
    monkeypatch.setattr(
        pipeline, "enrich", lambda db, top=None, on_progress=None: calls.append(("score", top))
    )

    pipeline.ingest_and_score(db=None, progress=lambda *a: None)

    assert calls == [("fetch",), ("score", pipeline.SCORE_DEPTH)]
    assert pipeline.SCORE_DEPTH == 25, "deeper than this and a fetch stops feeling quick"


@pytest.mark.parametrize(
    "boom",
    [
        RuntimeError("kb empty"),
        SystemExit("kb empty"),  # not an Exception — the original escape hatch
        KeyboardInterrupt(),
    ],
    ids=["exception", "base-exception", "interrupt"],
)
def test_a_crashed_run_is_always_marked_failed(sessions, monkeypatch, boom) -> None:
    """The `running` row IS the lock, so a step that dies without writing a
    terminal status disables every run button until the server restarts.

    This is not hypothetical: `enrich` used to raise `SystemExit` on an empty
    knowledge base, which is a `BaseException`, so it sailed past the `except
    Exception` here, was silently swallowed by the thread, and stranded the row
    at `running` forever. The handler must survive anything a step can raise.
    """
    monkeypatch.setattr(pipeline, "SessionLocal", sessions)
    monkeypatch.setattr(
        pipeline, "ingest_and_score", lambda db, progress: (_ for _ in ()).throw(boom)
    )

    with sessions() as db:
        run = PipelineRun(kind="ingest", message=LABELS["ingest"], total=0)
        db.add(run)
        db.commit()
        run_id = run.id

    pipeline._execute(run_id, "ingest")

    with sessions() as db:
        row = db.get(PipelineRun, run_id)
        assert row.status == "failed", "the lock is still held; every button stays dead"
        assert row.finished_at is not None
        assert row.error, "a failed run with no reason is a dead end for the user"


def test_an_empty_knowledge_base_is_a_catchable_error(sessions) -> None:
    """`SystemExit` here read like "stop the CLI", but `enrich` is a library
    function the API and the scheduler both call — and neither can catch it."""
    with sessions() as db, pytest.raises(RuntimeError) as caught:
        enrich(db)

    assert "Knowledge Base is empty" in str(caught.value)
