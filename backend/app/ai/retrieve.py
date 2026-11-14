"""Hybrid retrieval over the candidate knowledge base.

Given a job, find the accomplishments actually worth putting on the resume.

Two retrievers, because each fails where the other succeeds:

* **Vector (cosine similarity)** understands meaning — a chunk saying "built REST
  services" matches a JD asking for "backend API development" with no shared words.
  It is bad at exactness: it happily rates "Java" close to "JavaScript".
* **Lexical (exact term matching)** is the opposite — it never confuses Java with
  JavaScript, but it misses every paraphrase.

We run both and merge with **Reciprocal Rank Fusion**: each result scores
`1/(k + rank)` in each list and the scores are summed. RRF needs no score
calibration between the two systems (cosine distances and term counts are not
comparable numbers) — it only uses *ranks*, which is exactly why it is the
standard way to fuse heterogeneous retrievers.
"""
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import vectors
from app.ai.embeddings import embed_query
from app.db.models import KBChunk

# Standard RRF constant: damps the influence of the very top ranks so one
# retriever cannot dominate the fused list.
RRF_K = 60


def retrieve_all(
    db: Session, job_title: str, requirements: dict, profile_id: int | None = None
) -> list[KBChunk]:
    """Every chunk in the knowledge base, most relevant to this job first.

    Resume writing wants the whole career on the table: a real accomplishment
    that ranked 9th is still the right bullet for a section the top 8 say nothing
    about, and dropping it means an untailored section. Ordering still matters —
    a small model pays most attention to what it reads first — so this is the
    same fused ranking as `retrieve`, just without the cutoff.
    """
    ranked = retrieve(db, job_title, requirements, k=None, profile_id=profile_id)
    seen = {c.id for c in ranked}
    rest = [
        c for c in _profile_chunks(db, profile_id) if c.id not in seen
    ]
    return ranked + rest


def retrieve(
    db: Session,
    job_title: str,
    requirements: dict,
    k: int | None = 8,
    profile_id: int | None = None,
) -> list[KBChunk]:
    """Return the k most relevant KB chunks for this job, best first.

    `k=None` ranks everything the two retrievers found, with no cutoff.
    """
    skills = list(requirements.get("required_skills", [])) + list(
        requirements.get("preferred_skills", [])
    )
    query = ". ".join(
        [job_title, *requirements.get("responsibilities", [])[:5], *skills[:15]]
    ).strip()

    limit = k * 2 if k is not None else _total(db, profile_id)
    semantic = _vector_search(db, query or job_title, limit=limit, profile_id=profile_id)
    lexical = _lexical_search(db, skills, job_title, limit=limit, profile_id=profile_id)
    fused = _fuse(semantic, lexical)
    return fused if k is None else fused[:k]


def _profile_chunks(db: Session, profile_id: int | None) -> list[KBChunk]:
    query = select(KBChunk)
    if profile_id is not None:
        query = query.where((KBChunk.profile_id.is_(None)) | (KBChunk.profile_id == profile_id))
    return list(db.scalars(query))


def _total(db: Session, profile_id: int | None = None) -> int:
    return len(_profile_chunks(db, profile_id))


def _vector_search(
    db: Session, query: str, limit: int, profile_id: int | None = None
) -> list[KBChunk]:
    """Meaning-based arm: nearest chunks by cosine similarity.

    An exact scan in numpy rather than a database index — the knowledge base is
    one person's career, so this ranks tens of rows (see `app.ai.vectors`).
    """
    qvec = embed_query(query)
    chunks = _profile_chunks(db, profile_id)
    return [chunk for chunk, _ in vectors.rank(qvec, chunks)[:limit]]


def _lexical_search(
    db: Session,
    skills: list[str],
    job_title: str,
    limit: int,
    profile_id: int | None = None,
) -> list[KBChunk]:
    """Exactness arm: rank chunks by how many required terms they literally contain.

    Done in Python rather than SQL full-text because the KB is small (tens of
    chunks) and this keeps the matching rules identical to the ones the scoring
    engine already uses — no second, subtly different notion of "contains".
    """
    terms = {t for t in (_norm(s) for s in skills) if t}
    terms.update(w for w in _words(job_title) if len(w) > 3)
    if not terms:
        return []

    scored = []
    for chunk in _profile_chunks(db, profile_id):
        haystack = _norm(
            " ".join(
                [
                    chunk.title or "",
                    chunk.accomplishment or "",
                    chunk.impact or "",
                    " ".join(chunk.technologies or []),
                    " ".join(chunk.skills or []),
                ]
            )
        )
        hits = sum(1 for term in terms if _contains(haystack, term))
        if hits:
            scored.append((hits, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def _fuse(*rankings: list[KBChunk]) -> list[KBChunk]:
    """Reciprocal Rank Fusion over several ranked lists."""
    scores: dict[int, float] = {}
    by_id: dict[int, KBChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (RRF_K + rank + 1)
            by_id[chunk.id] = chunk
    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [by_id[chunk_id] for chunk_id, _ in ordered]


def _contains(haystack: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) is not None


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9+#.]{2,}", _norm(text)))


def _norm(text: str) -> str:
    """Collapse whitespace runs so multi-word skills match across line breaks."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]+", " ", (text or "").lower())).strip()
