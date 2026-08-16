"""Knowledge-base endpoints: add career items, list/delete chunks, semantic search.

Adding an item splits it into one chunk per accomplishment. Each chunk is
embedded from a *context-rich* string (title + accomplishment + technologies),
not just the raw bullet — more context produces a more useful vector.
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import vectors
from app.ai.embeddings import embed_passage, embed_query
from app.ai.parse import extract_text
from app.api import parse_jobs
from app.db.models import KBChunk
from app.db.session import get_db
from app.schemas import ChunkIn, KBChunkOut, KBItemIn, SearchResult

log = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


def _compose_chunk_text(
    title: str, accomplishment: str, technologies: list[str]
) -> str:
    """Build the string we actually embed for a chunk."""
    parts = [title.strip(), accomplishment.strip()]
    if technologies:
        parts.append("Technologies: " + ", ".join(technologies))
    return ". ".join(p for p in parts if p)


@router.post("/items", response_model=list[KBChunkOut], status_code=201)
def add_item(item: KBItemIn, db: Session = Depends(get_db)) -> list[KBChunk]:
    """Add a career item; create + embed one chunk per accomplishment."""
    chunks: list[KBChunk] = []
    for acc in item.accomplishments:
        text = _compose_chunk_text(item.title, acc.text, acc.technologies)
        chunk = KBChunk(
            type=item.type,
            title=item.title,
            context=item.context,
            company=item.company,
            date_range=item.date_range,
            accomplishment=acc.text,
            technologies=acc.technologies,
            skills=acc.skills,
            impact=acc.impact,
            embedding=embed_passage(text),
        )
        db.add(chunk)
        chunks.append(chunk)
    db.commit()
    for c in chunks:
        db.refresh(c)
    return chunks


@router.get("/chunks", response_model=list[KBChunkOut])
def list_chunks(db: Session = Depends(get_db)) -> list[KBChunk]:
    """List all stored chunks, newest first."""
    return list(db.scalars(select(KBChunk).order_by(KBChunk.created_at.desc())))


@router.delete("/chunks/{chunk_id}", status_code=204)
def delete_chunk(chunk_id: int, db: Session = Depends(get_db)) -> None:
    chunk = db.get(KBChunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    db.delete(chunk)
    db.commit()


@router.get("/search", response_model=list[SearchResult])
def search(q: str, k: int = 5, db: Session = Depends(get_db)) -> list[dict]:
    """Semantic search: embed the query, return the k nearest chunks by meaning."""
    qvec = embed_query(q)
    chunks = list(db.scalars(select(KBChunk)))
    results = []
    for chunk, similarity in vectors.rank(qvec, chunks)[:k]:
        data = KBChunkOut.model_validate(chunk).model_dump()
        data["similarity"] = round(similarity, 4)
        results.append(data)
    return results


@router.post("/parse", status_code=202)
def start_parse(
    files: list[UploadFile] = File(...),
    kinds: list[str] = Form(default=[]),
) -> dict:
    """Begin parsing uploaded documents. Returns a job to poll — nothing is saved.

    Parsing is a background job rather than a long request because a real CV is
    several model calls and a laptop model is slow: held open, the request would
    be at the mercy of every proxy and browser timeout between here and the tab,
    and the user would stare at a spinner with no idea whether it was working.

    Text extraction happens here, while the upload is still in memory; only the
    slow part is handed to the thread.
    """
    documents: list[tuple[str, str, str | None]] = []
    errors: list[str] = []
    for i, f in enumerate(files):
        kind = kinds[i] if i < len(kinds) and kinds[i] else None
        try:
            documents.append((f.filename or "document", extract_text(f.filename or "", f.file.read()), kind))
        except Exception as e:  # noqa: BLE001 - report, keep going
            log.exception("Extracting text from %s failed", f.filename)
            errors.append(f"{f.filename}: {e}")

    if not documents:
        raise HTTPException(status_code=400, detail="; ".join(errors) or "no readable files")

    job = parse_jobs.start(documents, errors)
    return job


@router.get("/parse/{job_id}")
def parse_status(job_id: str) -> dict:
    job = parse_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="parse job not found")
    return job


@router.post("/chunks/bulk", response_model=list[KBChunkOut], status_code=201)
def save_chunks(chunks: list[ChunkIn], db: Session = Depends(get_db)) -> list[KBChunk]:
    """Embed and store a list of reviewed chunks."""
    created: list[KBChunk] = []
    for c in chunks:
        text = _compose_chunk_text(c.title, c.accomplishment, c.technologies)
        row = KBChunk(
            type=c.type,
            title=c.title,
            context=c.context,
            company=c.company,
            date_range=c.date_range,
            accomplishment=c.accomplishment,
            technologies=c.technologies,
            skills=c.skills,
            impact=c.impact,
            embedding=embed_passage(text),
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created
