"""Enrichment: extract requirements, embed each job, score it against the KB.

    python -m app.ingestion.enrich [--limit N]

Split from `run` (ingestion) because the two have completely different costs.
Ingestion is a few seconds of HTTP. Extraction is ~25s of local LLM per job, so
this stage is built to be **resumable**: work is cached by the job's
`content_hash` and re-running only processes what is genuinely new or changed.

Matching itself is cheap and deterministic, so it is always recomputed — your
scores stay correct after you edit your knowledge base.
"""
import argparse
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.extract import extract_requirements
from app.ai.match import (
    DEFAULT_ROLE_FAMILIES,
    CandidateIndex,
    embed_job,
    score,
    score_cheap,
)
from app.db.models import (
    Job,
    JobEmbedding,
    JobRequirements,
    KBChunk,
    Match,
    Preferences,
)
from app.db.session import SessionLocal
from app.ingestion.role_family import classify
from app.ingestion.seniority import is_fresher_friendly

log = logging.getLogger(__name__)


def enrich(
    db: Session,
    top: int = 100,
    limit: int | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Two-tier scoring over every active job.

    * **Tier 1 (no LLM, every job).** Deterministic filters, then embed the job
      and rank it on semantic similarity + keyword overlap. Milliseconds each,
      so thousands of jobs are tractable.
    * **Tier 2 (LLM, top `top` only).** Extract requirements and compute the
      full four-feature score for the best candidates from tier 1.

    Spending 25s per job on all of them would take days; spending it on the
    hundred you might actually apply to takes half an hour.
    """
    chunks = list(db.scalars(select(KBChunk)))
    candidate = CandidateIndex(chunks)
    if candidate.is_empty:
        # A plain error, not SystemExit: this runs inside the API's background
        # thread as often as it does a CLI, and SystemExit is a BaseException
        # that every `except Exception` in the app lets through.
        raise RuntimeError(
            "Your Knowledge Base is empty — add your experience there first, "
            "then run this again."
        )

    preferences = db.scalar(select(Preferences))
    families = set(getattr(preferences, "role_families", None) or DEFAULT_ROLE_FAMILIES)

    jobs = list(db.scalars(select(Job).where(Job.status == "active")))
    counts = {"filtered": 0, "estimated": 0, "extracted": 0, "cached": 0}

    # Progress spans both tiers: tier 1 touches every job quickly, tier 2 touches
    # at most `top` jobs slowly. Reporting them as one scale would make the bar
    # race to 95% and then appear frozen for half an hour.
    tier2_budget = min(top, limit if limit is not None else top)

    # ---- Tier 1: filter + cheap score, for everything ----
    shortlist: list[tuple[float, Job]] = []
    for index, job in enumerate(jobs, start=1):
        if on_progress and index % 25 == 0:
            on_progress(index, len(jobs), f"Ranking jobs ({index}/{len(jobs)})")
        skip_reason = _cheap_skip(job.title, families)
        if skip_reason:
            _save_match(db, job.id, _filtered_result(skip_reason))
            counts["filtered"] += 1
            continue

        # If this job was already extracted on an earlier run, score it at full
        # tier now. Overwriting a full match with a cheap one would throw away
        # LLM work we already paid for and silently downgrade the row.
        existing = db.get(JobRequirements, job.id)
        if existing is not None and existing.source_hash == job.content_hash:
            vector = _embedding(db, job, _as_dict(existing))
            result = score(job, _as_dict(existing), vector, candidate, preferences)
            counts["cached"] += 1
        else:
            vector = _embedding(db, job, {})
            result = score_cheap(job, vector, candidate, preferences)
            counts["estimated"] += 1

        _save_match(db, job.id, result)
        if not result["hard_filtered"]:
            shortlist.append((result["score"], job))
    db.commit()

    # ---- Tier 2: full extraction for the most promising ----
    shortlist.sort(key=lambda pair: pair[0], reverse=True)
    budget = limit if limit is not None else top
    for _, job in shortlist[:top]:
        if counts["extracted"] >= budget:
            break
        if on_progress:
            on_progress(
                counts["extracted"],
                tier2_budget,
                f"Reading job descriptions ({counts['extracted']}/{tier2_budget})",
            )
        requirements, was_cached = _requirements(db, job)
        if was_cached:
            continue  # already scored at full tier above
        counts["extracted"] += 1
        vector = _embedding(db, job, requirements)
        _save_match(db, job.id, score(job, requirements, vector, candidate, preferences))

    db.commit()
    if on_progress:
        on_progress(tier2_budget, tier2_budget, "Done")
    return counts


def _filtered_result(reason: str) -> dict:
    return {
        "score": 0.0,
        "features": {},
        "confidence": 0.0,
        "hard_filtered": True,
        "filter_reason": reason,
        "tier": "estimated",
        "why": {"skipped": reason},
    }


def _cheap_skip(title: str, families: set[str]) -> str:
    """Reason to skip this job without calling the LLM, or "" to proceed."""
    family = classify(title)
    if family not in families:
        return f"not a target role ({family})"
    if not is_fresher_friendly(title):
        return "senior title"
    return ""


def rescore_all(db: Session) -> dict:
    """Recompute every match from cached extractions — no LLM, so it is seconds.

    This is what makes preferences feel instant: changing a filter re-runs the
    deterministic half of the pipeline only.
    """
    chunks = list(db.scalars(select(KBChunk)))
    candidate = CandidateIndex(chunks)
    preferences = db.scalar(select(Preferences))
    families = set(getattr(preferences, "role_families", None) or DEFAULT_ROLE_FAMILIES)

    counts = {"scored": 0, "filtered": 0}
    for job in db.scalars(select(Job).where(Job.status == "active")):
        skip_reason = _cheap_skip(job.title, families)
        if skip_reason:
            _save_match(db, job.id, _filtered_result(skip_reason))
            counts["filtered"] += 1
            continue

        # Embed it now if it has never been embedded. This used to skip such a
        # job and leave whatever match row it already had, which is wrong in the
        # exact case that matters: a job the filters used to reject and now
        # accept keeps its old rejection and stays invisible. Widening a filter
        # appeared to do nothing.
        #
        # Cheap enough to belong here. This is a local sentence-transformer, not
        # an LLM, and only jobs that survive the filters above ever reach it, so
        # a re-score embeds a handful of newly eligible jobs rather than
        # thousands of rejected ones.
        embedding = db.get(JobEmbedding, job.id)
        vector = (
            list(embedding.embedding) if embedding is not None else _embedding(db, job, {})
        )

        # Re-score at whatever tier this job already has data for.
        row = db.get(JobRequirements, job.id)
        result = (
            score(job, _as_dict(row), vector, candidate, preferences)
            if row is not None
            else score_cheap(job, vector, candidate, preferences)
        )
        _save_match(db, job.id, result)
        counts["scored"] += 1
        counts["filtered"] += int(result["hard_filtered"])

    db.commit()
    return counts


def enrich_one(db: Session, job: Job) -> dict:
    """Extract, embed and score a single job right now.

    Used by the manual-JD flow, where the user is waiting for this one job rather
    than running the nightly batch.
    """
    chunks = list(db.scalars(select(KBChunk)))
    candidate = CandidateIndex(chunks)
    preferences = db.scalar(select(Preferences))
    requirements, _ = _requirements(db, job)
    vector = _embedding(db, job, requirements)
    result = score(job, requirements, vector, candidate, preferences)
    _save_match(db, job.id, result)
    db.commit()
    return result


def _requirements(db: Session, job: Job) -> tuple[dict, bool]:
    """Extract requirements, reusing a previous run when the posting is unchanged."""
    row = db.get(JobRequirements, job.id)
    if row is not None and row.source_hash == job.content_hash:
        return _as_dict(row), True

    log.info("extracting: %s | %s", job.company, job.title[:60])
    data = extract_requirements(job.title, job.description)

    if row is None:
        row = JobRequirements(job_id=job.id)
        db.add(row)
    row.required_skills = data["required_skills"]
    row.preferred_skills = data["preferred_skills"]
    row.responsibilities = data["responsibilities"]
    row.seniority = data["seniority"]
    row.min_years = data["min_years"]
    row.confidence = data["confidence"]
    row.source_hash = job.content_hash
    db.commit()
    return data, False


def _embedding(db: Session, job: Job, requirements: dict) -> list[float]:
    """Embed the job once per content version."""
    row = db.get(JobEmbedding, job.id)
    if row is not None and row.source_hash == job.content_hash:
        return list(row.embedding)

    vector = embed_job(job.title, requirements, job.description)
    if row is None:
        row = JobEmbedding(job_id=job.id, embedding=vector)
        db.add(row)
    else:
        row.embedding = vector
    row.source_hash = job.content_hash
    db.commit()
    return vector


def _save_match(db: Session, job_id: int, result: dict) -> None:
    row = db.get(Match, job_id) or Match(job_id=job_id)
    features = result.get("features", {})
    row.score = result["score"]
    row.f_semantic = features.get("semantic", 0.0)
    row.f_keyword = features.get("keyword_overlap", 0.0)
    row.f_required_cov = features.get("required_coverage", 0.0)
    row.f_preferred_cov = features.get("preferred_coverage", 0.0)
    row.f_preference_fit = features.get("preference_fit", 0.0)
    row.confidence = result["confidence"]
    row.hard_filtered = result["hard_filtered"]
    row.filter_reason = result["filter_reason"]
    row.tier = result.get("tier", "estimated")
    row.why = result["why"]
    db.add(row)


def _as_dict(row: JobRequirements) -> dict:
    return {
        "required_skills": list(row.required_skills or []),
        "preferred_skills": list(row.preferred_skills or []),
        "responsibilities": list(row.responsibilities or []),
        "seniority": row.seniority,
        "min_years": row.min_years,
        "confidence": row.confidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract, embed and score jobs.")
    parser.add_argument(
        "--top", type=int, default=100, help="how many top-ranked jobs get full LLM extraction"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="cap NEW extractions this run (~25s each)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal() as db:
        counts = enrich(db, top=args.top, limit=args.limit)

    print(
        f"\nfiltered={counts['filtered']} (no LLM)  "
        f"estimated={counts['estimated']} (tier 1, embeddings only)  "
        f"extracted={counts['extracted']} (tier 2, new LLM calls)  "
        f"cached={counts['cached']}"
    )


if __name__ == "__main__":
    main()
