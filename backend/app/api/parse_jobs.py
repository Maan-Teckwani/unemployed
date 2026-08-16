"""In-memory registry of running document-parse jobs.

Deliberately not a table. A parse job exists only until the user reviews the
chunks it proposed — minutes, never across a restart — and its result is a
throwaway list the user is about to edit anyway. A migration for that would be
ceremony around nothing.

The trade is explicit: restart the backend mid-parse and the job is gone, and
the user uploads again.
"""
import logging
import threading
import uuid

from app.ai.parse import parse_to_chunks, segment

log = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def start(documents: list[tuple[str, str, str | None]], errors: list[str]) -> dict:
    """Kick off parsing for (filename, text, kind) triples and return the job."""
    job_id = uuid.uuid4().hex
    # Total is segments, not files: one long CV is many model calls, and a bar
    # that sits at "0/1" for six minutes is indistinguishable from a hang.
    total = sum(len(segment(text)) for _, text, _ in documents)
    job = {
        "id": job_id,
        "status": "running",
        "done": 0,
        "total": total,
        "message": f"Reading {documents[0][0]}",
        "chunks": [],
        "errors": list(errors),
    }
    with _lock:
        _jobs[job_id] = job

    threading.Thread(target=_run, args=(job_id, documents), daemon=True).start()
    return _public(job)


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return _public(job) if job else None


def _run(job_id: str, documents: list[tuple[str, str, str | None]]) -> None:
    job = _jobs[job_id]
    try:
        for filename, text, kind in documents:
            job["message"] = f"Reading {filename}"

            def advance() -> None:
                job["done"] += 1
                job["message"] = f"Read {job['done']} of {job['total']} sections"

            try:
                job["chunks"].extend(parse_to_chunks(text, kind, on_segment=advance))
            except Exception as e:  # noqa: BLE001 - one bad file must not sink the batch
                log.exception("Parsing %s failed", filename)
                job["errors"].append(f"{filename}: {e}")

        job["status"] = "done"
        job["message"] = f"Found {len(job['chunks'])} accomplishment(s)"
    except Exception as e:  # noqa: BLE001 - the UI needs the reason
        log.exception("Parse job %s failed", job_id)
        job["status"] = "failed"
        job["message"] = str(e)[:500]


def _public(job: dict) -> dict:
    """Chunks only travel once the job is finished — a half-parsed list would
    invite the user to start editing something still being appended to."""
    return {
        "id": job["id"],
        "status": job["status"],
        "done": job["done"],
        "total": job["total"],
        "message": job["message"],
        "errors": job["errors"],
        "chunks": job["chunks"] if job["status"] == "done" else [],
    }
