"""The daily ingestion pipeline: fetch -> filter -> dedupe -> upsert -> expire.

Three properties matter more than speed here:

* **Idempotent** — re-running changes nothing. Identity is (source, external_id),
  so a second run updates rows instead of inserting duplicates.
* **Isolated** — each company is fetched in its own try/except and gets its own
  `ingestion_runs` row. One dead board cannot abort the others.
* **Safe expiry** — jobs are only expired after a *successful* fetch. If a board
  errors we keep what we have, instead of wrongly marking everything gone.
"""
import hashlib
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import RawJob
from app.connectors.registry import CONNECTORS, Company, load_companies
from app.db.models import IngestionRun, Job, Preferences
from app.ingestion.relevance import DEFAULT_REGION, is_relevant

log = logging.getLogger(__name__)

# How many boards to read at once. Waiting on someone else's web server is not
# work, so this is bounded by politeness rather than by cores. The same number
# the discovery sweep has used since it was written.
FETCH_WORKERS = 8


def run_ingestion(
    db: Session,
    companies: list[Company] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[IngestionRun]:
    """Ingest every configured company. Returns one audit row per company.

    Reading the boards and writing the database are two separate passes. Nearly
    all the wall clock is the first one: ninety six boards at two seconds each
    is three minutes of sitting still, and one slow board used to add thirty
    seconds to everyone else's wait. So the boards are read at once, and the
    database is written afterwards on this thread, one company at a time. A
    Session belongs to one thread, and this way it never leaves this one.

    `on_progress(done, total, message)` lets the UI show progress. It is
    optional so the CLI keeps working untouched.
    """
    preferences = db.scalar(select(Preferences))
    region = getattr(preferences, "region", None) or DEFAULT_REGION

    targets = companies if companies is not None else load_companies(db)
    if not targets:
        return []

    fetched = _fetch_all(targets, region, on_progress)
    runs = [_store(db, company, region, raw, error) for company, raw, error in fetched]
    if on_progress:
        on_progress(len(targets), len(targets), "Done")
    return runs


def _fetch_all(
    targets: list[Company], region: str, on_progress: Callable | None
) -> list[tuple[Company, list[RawJob] | None, Exception | None]]:
    """Read every board at once. Network only: nothing here touches the database.

    Failures are returned rather than raised, so one dead board still gets its
    own audit row and the rest of the run is unaffected. Results come back in
    the order the companies were given, not the order they answered, so the
    audit rows stay stable between runs.
    """
    results: dict[int, tuple[list[RawJob] | None, Exception | None]] = {}
    with ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, len(targets))) as pool:
        futures = {
            pool.submit(_fetch_one, company, region): index
            for index, company in enumerate(targets)
        }
        for done, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            results[index] = future.result()
            if on_progress:
                on_progress(done, len(targets), f"Reading job boards ({done}/{len(targets)})")
    return [(company, *results[i]) for i, company in enumerate(targets)]


def _fetch_one(
    company: Company, region: str
) -> tuple[list[RawJob] | None, Exception | None]:
    try:
        return CONNECTORS[company.source](company.token, company.name, region), None
    except Exception as e:  # noqa: BLE001 - isolate this source, keep the run going
        log.warning("ingest failed for %s/%s: %s", company.source, company.token, e)
        return None, e


def _store(
    db: Session,
    company: Company,
    region: str,
    raw_jobs: list[RawJob] | None,
    error: Exception | None,
) -> IngestionRun:
    """Write one company's jobs, in one transaction."""
    # The counters are set here rather than left to the column defaults, which
    # SQLAlchemy applies at INSERT. This used to commit the row before counting
    # anything, so the defaults had landed by the time the first `+=` ran.
    # Without that commit the attributes are None until something happens to
    # flush, and "something happens to flush" is not a thing to depend on.
    run = IngestionRun(
        source=company.source,
        company=company.name,
        jobs_seen=0,
        jobs_new=0,
        jobs_updated=0,
        jobs_expired=0,
    )
    db.add(run)

    if error is not None:
        run.ok, run.error, run.finished_at = False, str(error)[:2000], _now()
        db.commit()
        return run

    relevant = [j for j in raw_jobs if is_relevant(j.location, j.remote, j.title, region)]
    seen_ids = []
    for raw in relevant:
        created = _upsert(db, raw)
        seen_ids.append(raw.external_id)
        run.jobs_new += int(created)
        run.jobs_updated += int(not created)

    run.jobs_seen = len(relevant)
    run.jobs_expired = _expire_missing(db, company, seen_ids)
    run.finished_at = _now()
    # One commit for the whole company. It used to be one per job, which is a
    # couple of thousand transactions per run against a file another thread is
    # reading.
    db.commit()
    return run


def _upsert(db: Session, raw: RawJob) -> bool:
    """Insert or refresh one job in the open transaction. True if newly created.

    Does not commit. The caller commits once per company, so a board that dies
    halfway leaves that company unchanged rather than half written.
    """
    existing = db.scalar(
        select(Job).where(Job.source == raw.source, Job.external_id == raw.external_id)
    )
    content_hash = _sha(f"{raw.title}\n{raw.description}")

    if existing is None:
        # Cross-source duplicate: the same role already came from another board.
        fingerprint = _sha(f"{_norm(raw.company)}|{_norm(raw.title)}")
        if db.scalar(select(Job).where(Job.fingerprint == fingerprint)) is not None:
            return False
        db.add(
            Job(
                source=raw.source,
                external_id=raw.external_id[:200],
                company=_fit(raw.company, 200),
                title=_fit(raw.title, 400),
                location=_fit(raw.location, 300),
                remote=raw.remote,
                description=raw.description,
                apply_url=_fit(raw.apply_url, 1000),
                posted_at=raw.posted_at,
                content_hash=content_hash,
                fingerprint=fingerprint,
            )
        )
        return True

    existing.last_seen = _now()
    existing.status = "active"  # a job that reappears is live again
    if existing.content_hash != content_hash:  # incremental: only touch real changes
        existing.title = _fit(raw.title, 400)
        existing.description = raw.description
        existing.location = _fit(raw.location, 300)
        existing.remote = raw.remote
        existing.apply_url = _fit(raw.apply_url, 1000)
        existing.content_hash = content_hash
    return False


def _expire_missing(db: Session, company: Company, seen_ids: list[str]) -> int:
    """Mark active jobs from this company that the source no longer lists."""
    stale = db.scalars(
        select(Job).where(
            Job.source == company.source,
            Job.company == company.name,
            Job.status == "active",
            Job.external_id.notin_(seen_ids) if seen_ids else True,
        )
    ).all()
    for job in stale:
        job.status = "expired"
    return len(stale)


def _fit(text: str, limit: int) -> str:
    """Trim a field to its column width.

    Real boards break assumptions: New Relic lists 20+ cities in one `location`
    string, which is past VARCHAR(300) and aborted a whole ingestion run. The
    pipeline truncates centrally so one verbose source cannot take down others.
    """
    return (text or "")[:limit]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    """Loose normalization so trivial formatting differences still match."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _now() -> datetime:
    return datetime.now(UTC)
