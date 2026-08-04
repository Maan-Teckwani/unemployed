"""RAG resume generation: rewrite real accomplishments for one specific job.

The model is never asked "write a resume". It is given a numbered list of the
candidate's *verified* accomplishments and asked to rephrase selected ones for
this job. That distinction is the whole design — it can only reword facts that
already exist.

Three independent layers stop invention, because prompts alone are not a
guarantee:

1. **Retrieval** — only real KB chunks ever enter the context window.
2. **Prompt** — explicit "use only these facts, omit rather than invent, cite the
   id you used".
3. **Validation** — every produced bullet must cite a real chunk id, and every
   number in a bullet must already appear in the chunk it cites. A bullet that
   fails is dropped, not shipped. Invented metrics ("improved performance by
   40%") are the single most dangerous resume hallucination, so they are checked
   mechanically rather than trusted.
"""
import re
from collections import defaultdict

from app.ai.llm import fits_context, generate_json
from app.ai.sections import MAX_TOTAL, quota_for, section_for
from app.db.models import KBChunk

# Kept as the number quoted to the model, not as a hard stop on the output.
# Sections are budgeted individually in `_validate_bullets`, because a single
# global cap applied in arrival order let eight Experience bullets use the whole
# resume and leave Projects, Education and Certifications printing nothing.
MAX_BULLETS = MAX_TOTAL

# ONE job per call. Asking a small model for summary + skills + bullets in a
# single schema makes it answer the easy parts and silently drop the hard one,
# so rewriting bullets — the only genuinely generative task here — gets the whole
# call and the smallest schema that can express the answer.
_SYSTEM = """You rewrite a candidate's REAL accomplishments as resume bullets for one specific job.

You are given the candidate's complete record. Your job is selection and phrasing, not invention.

SELECTION
- Read every numbered accomplishment before choosing. The best evidence for this job is often not the first one listed.
- Choose the ones this job actually asks for, strongest first. Fewer, sharper bullets beat a complete list.
- Skip anything irrelevant to this job, however impressive.

PHRASING
- Start with a strong past-tense verb. One sentence, max 30 words.
- Lead with the outcome or the thing built, then how.
- Where the accomplishment genuinely supports it, use the job's own words for the same thing: if it says "RESTful APIs" and the accomplishment says "REST services", write "RESTful APIs". Matching the job's vocabulary is how automated screeners find you.

TRUTH
- Use ONLY the numbered accomplishments provided. Never invent experience, employers, technologies or metrics.
- Every bullet MUST include "source_id": the number of the accomplishment it came from.
- Never introduce a number, percentage or metric that is not already in that accomplishment.
- Never claim a skill the job wants but the accomplishments do not show.

Respond with JSON in exactly this shape:
{"bullets":[{"source_id":1,"text":"Built X using Y, serving Z users"},{"source_id":3,"text":"..."}]}"""


def generate(profile, job, requirements: dict, chunks: list[KBChunk]) -> dict:
    """Generate a tailored resume. Returns bullets already validated for truthfulness."""
    if not chunks:
        return {"summary": "", "skills": [], "bullets": [], "rejected": []}

    # The whole knowledge base goes into one call, and a knowledge base has no
    # size limit. Past the context window Ollama drops the front of the prompt
    # without saying so, which reads as the model having ignored the earliest
    # half of a career. Dropping the least relevant chunks ourselves is worse
    # than sending everything and better than being silently truncated: the
    # chunks arrive ranked, so what goes is what mattered least to this job.
    chunks = _fit_to_window(job, requirements, chunks)

    prompt = _build_prompt(job, requirements, chunks)
    raw = generate_json(_SYSTEM, prompt, timeout=300, max_tokens=2000)

    by_id = {i + 1: chunk for i, chunk in enumerate(chunks)}
    bullets, rejected = _validate_bullets(raw.get("bullets"), by_id)

    return {
        # No LLM summary: it burns one-page budget and adds invention risk for
        # little value. The user can write their own in the editor.
        "summary": "",
        "skills": select_skills(requirements, chunks),
        "bullets": bullets,
        "rejected": rejected,
    }


def select_skills(requirements: dict, chunks: list[KBChunk], limit: int = 18) -> list[str]:
    """The skills section, computed rather than generated.

    It is exactly "what this job asks for" ∩ "what the KB actually evidences",
    required first. Deterministic, so it can never claim a skill the candidate
    does not have, and it always speaks the JD's vocabulary.
    """
    evidence = _norm(
        " ".join(
            f"{c.title} {c.accomplishment} {c.impact or ''} "
            f"{' '.join(c.technologies or [])} {' '.join(c.skills or [])}"
            for c in chunks
        )
    )

    selected: list[str] = []
    for skill in list(requirements.get("required_skills", [])) + list(
        requirements.get("preferred_skills", [])
    ):
        name = str(skill).strip()
        if name and _evidenced(name, evidence) and name.lower() not in {s.lower() for s in selected}:
            selected.append(name)

    # Top up with the candidate's own strongest technologies so the section is
    # never near-empty just because the JD listed few skills.
    for chunk in chunks:
        for tech in chunk.technologies or []:
            name = str(tech).strip()
            if len(selected) >= limit:
                break
            if name and name.lower() not in {s.lower() for s in selected}:
                selected.append(name)
    return selected[:limit]


def _evidenced(name: str, evidence: str) -> bool:
    term = _norm(name)
    if not term:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", evidence) is not None


def _fit_to_window(job, requirements: dict, chunks: list[KBChunk]) -> list[KBChunk]:
    """Trim the tail of the ranked list until the prompt fits the context window.

    Halving rather than dropping one at a time: this is a loop over string
    building, and a knowledge base large enough to overflow is large enough that
    one-by-one would rebuild the prompt hundreds of times.
    """
    kept = list(chunks)
    while kept and not fits_context(_SYSTEM, _build_prompt(job, requirements, kept), 2000):
        if len(kept) == 1:
            break  # one enormous chunk. Send it and let the model see what fits.
        kept = kept[: max(1, len(kept) // 2)]
    return kept


def _build_prompt(job, requirements: dict, chunks: list[KBChunk]) -> str:
    lines = [
        f"TARGET JOB: {job.title} at {job.company}",
        f"Required skills: {', '.join(requirements.get('required_skills', [])) or 'not specified'}",
        f"Preferred skills: {', '.join(requirements.get('preferred_skills', [])) or 'not specified'}",
        "",
        "CANDIDATE'S VERIFIED ACCOMPLISHMENTS (the only facts you may use):",
    ]
    for i, chunk in enumerate(chunks, start=1):
        context = " | ".join(
            part for part in [chunk.company, chunk.date_range, chunk.context] if part
        )
        tech = ", ".join(chunk.technologies or [])
        lines.append(f"\n[{i}] {chunk.title}" + (f" ({context})" if context else ""))
        lines.append(f"    {chunk.accomplishment}")
        if tech:
            lines.append(f"    Technologies: {tech}")
        if chunk.impact:
            lines.append(f"    Impact: {chunk.impact}")
    lines.append(
        f"\nWrite at most {MAX_BULLETS} bullets, most relevant first, each citing its source_id."
    )
    return "\n".join(lines)


def _validate_bullets(raw_bullets, by_id: dict[int, KBChunk]) -> tuple[list[dict], list[dict]]:
    """Keep only bullets that trace to a real chunk and invent no new numbers."""
    kept: list[dict] = []
    rejected: list[dict] = []
    used: dict[str, int] = defaultdict(int)
    if not isinstance(raw_bullets, list):
        return kept, rejected

    for item in raw_bullets:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        source_id = _as_int(item.get("source_id"))
        if not text:
            continue

        chunk = by_id.get(source_id)
        if chunk is None:
            rejected.append({"text": text, "reason": "cites no valid source accomplishment"})
            continue

        invented = _invented_numbers(text, chunk)
        if invented:
            rejected.append(
                {"text": text, "reason": f"invented metric(s) not in source: {', '.join(invented)}"}
            )
            continue

        section = section_for(chunk.type)
        # Budgeted per section rather than globally. Bullets arrive strongest
        # first, so a full section drops its weakest candidates and every other
        # section still gets to print.
        if used[section] >= quota_for(section):
            continue

        used[section] += 1
        kept.append(
            {
                "text": text,
                "source_chunk_ids": [chunk.id],
                "section": section,
                "title": chunk.title,
                "context": chunk.context,
                "company": chunk.company,
                "date_range": chunk.date_range,
            }
        )
        if len(kept) >= MAX_TOTAL:
            break
    return kept, rejected


def _invented_numbers(text: str, chunk: KBChunk) -> list[str]:
    """Any figure in the bullet must already exist in its source accomplishment."""
    source = " ".join(
        [chunk.accomplishment or "", chunk.impact or "", chunk.title or "",
         " ".join(chunk.technologies or [])]
    )
    source_numbers = set(_numbers(source))
    return [n for n in _numbers(text) if n not in source_numbers]


def _numbers(text: str) -> list[str]:
    """Digit groups, ignoring those glued to words (python3, s3, ipv6)."""
    return re.findall(r"(?<![A-Za-z])(\d[\d,.]*)", text or "")


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _norm(text: str) -> str:
    """Collapse whitespace runs so multi-word skills match across line breaks."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]+", " ", (text or "").lower())).strip()
