"""Grounded interview preparation generation."""
from app.ai.llm import generate_json

SYSTEM = """You create interview preparation from supplied evidence only.
Never invent employers, metrics, technologies, responsibilities, products, or
company facts. Every answer must cite one or more supplied KB chunk IDs, or say
that the evidence is insufficient. Return JSON with keys questions and
talking_points. questions is a list of {question, answer, source_chunk_ids}.
Keep answers concise and honest; distinguish a suggested angle from a fact."""


def generate(job: dict, requirements: dict, evidence: list[dict]) -> dict:
    prompt = f"""JOB (stored posting):
{job['title']} at {job['company']}
{job.get('description', '')}

EXTRACTED REQUIREMENTS:
{requirements}

CANDIDATE EVIDENCE (the only allowed source for candidate claims):
{evidence}

Create 5 likely questions (mix role-specific and behavioral) and 3 talking
points. Use exact source_chunk_ids from the evidence. If a question cannot be
answered from evidence, answer with a transparent preparation instruction and
an empty source_chunk_ids list."""
    raw = generate_json(SYSTEM, prompt, timeout=300, max_tokens=1800)
    questions = []
    valid_ids = {item["id"] for item in evidence}
    for item in raw.get("questions", []):
        if not isinstance(item, dict) or not item.get("question") or not item.get("answer"):
            continue
        ids = []
        for value in item.get("source_chunk_ids", []):
            try:
                candidate_id = int(value)
            except (TypeError, ValueError):
                continue
            if candidate_id in valid_ids:
                ids.append(candidate_id)
        questions.append({
            "question": str(item["question"]),
            "answer": str(item["answer"]),
            "source_chunk_ids": ids,
        })
    points = [str(p) for p in raw.get("talking_points", []) if str(p).strip()]
    if not questions:
        raise ValueError("model returned no grounded interview questions")
    return {"questions": questions[:8], "talking_points": points[:6],
            "source_chunk_ids": sorted({i for q in questions for i in q["source_chunk_ids"]})}


def summarize_company(company_name: str, facts: list[dict], jobs: list[dict]) -> dict:
    """Summarize only stored company notes and stored job postings."""
    prompt = f"""Company: {company_name}
STORED COMPANY NOTES:
{facts}
STORED JOB POSTINGS:
{jobs}

Return JSON with keys overview, themes, interview_signals, and source_ids.
Only state facts supported by the supplied text. Use source_ids containing
integers from the supplied note IDs or job IDs. If evidence is absent, say so."""
    raw = generate_json(SYSTEM, prompt, timeout=300, max_tokens=1200)
    source_ids = []
    for value in raw.get("source_ids", []):
        try:
            source_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return {
        "company_name": company_name,
        "overview": str(raw.get("overview", "No stored company evidence.")),
        "themes": [str(x) for x in raw.get("themes", [])],
        "interview_signals": [str(x) for x in raw.get("interview_signals", [])],
        "source_ids": source_ids,
    }
