"""Explainable matching: how well does the candidate's KB fit one job?

Deliberately NOT "ask the LLM if this is a good match". A single opaque number
cannot answer "why 62%?", cannot be tuned, and changes its mind between runs.
Instead we compute five independent, inspectable features and combine them with
a transparent weighted sum.

    score = 0.30*required_coverage
          + 0.25*semantic_similarity
          + 0.15*preferred_coverage
          + 0.15*keyword_overlap
          + 0.15*preference_fit

Why these weights: for a fresher, whether you actually have the *required*
skills dominates. Semantic similarity is next — it catches relevance that exact
strings miss ("built REST APIs" vs "backend services"). Preferred skills and raw
keyword overlap are useful tie-breakers, not decisions. `preference_fit` is what
the user asked for (region, remote, preferred cities) and joined the other four
once the preferences table existed.

Two of the five need an extracted job description, and extraction costs about
thirty seconds of local LLM per job. `score_cheap` below renormalises over the
three that do not, so every job gets an honest estimate on the same scale and
only the shortlist pays for the rest. WEIGHTS is the single source of truth for
both paths; changing a number here changes both.
"""
import re

import numpy as np

from app.ai.embeddings import embed_query
from app.ingestion.cities import resolve as resolve_city
from app.ingestion.experience import required_years
from app.ingestion.role_family import DEFAULT_FAMILIES, classify
from app.ingestion.seniority import is_fresher_friendly

WEIGHTS = {
    "required_coverage": 0.30,
    "semantic": 0.25,
    "preferred_coverage": 0.15,
    "keyword_overlap": 0.15,
    "preference_fit": 0.15,
}

# Fallbacks used only when no preferences row exists yet.
DEFAULT_MAX_YEARS = 1
DEFAULT_ALLOWED_SENIORITY = ("intern", "entry")
DEFAULT_ROLE_FAMILIES = DEFAULT_FAMILIES
# Levels a 0-experience candidate cannot reach whatever the years field says.
OUT_OF_REACH_LEVELS = {"senior", "lead"}
# Below this, an extraction is too weak to justify hiding a job from the user.
TRUST_THRESHOLD = 0.5

# Average of the best few chunks, not the single best: one lucky chunk should
# not make an unrelated job look like a great fit.
TOP_K = 3

# Common shorthand so "JS" and "JavaScript" are not treated as different skills.
_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "postgres": "postgresql",
    "psql": "postgresql",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "reactjs": "react",
    "react.js": "react",
    "nodejs": "node",
    "node.js": "node",
    "nextjs": "next.js",
    "golang": "go",
    "gcp": "google cloud",
    "oop": "object oriented programming",
    "ci/cd": "cicd",
    "restful": "rest",
    "rest api": "rest",
    "rest apis": "rest",
}

_STOPWORDS = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this", "that",
    "your", "from", "who", "all", "can", "not", "but", "any", "how", "its", "was",
    "job", "role", "team", "work", "working", "experience", "years", "year", "skills",
    "ability", "strong", "good", "excellent", "responsibilities", "requirements",
    "candidate", "company", "business", "new", "including", "using", "well", "other",
    "more", "must", "should", "would", "across", "within", "their", "them", "they",
}


class CandidateIndex:
    """Everything about the candidate that matching needs, computed once."""

    def __init__(self, chunks) -> None:
        self.vectors = np.array([c.embedding for c in chunks], dtype=np.float32)
        terms: set[str] = set()
        text_parts: list[str] = []
        for c in chunks:
            terms.update(_norm(s) for s in (c.technologies or []))
            terms.update(_norm(s) for s in (c.skills or []))
            text_parts += [c.title or "", c.accomplishment or "", c.impact or ""]
            text_parts += list(c.technologies or []) + list(c.skills or [])
        self.terms = {t for t in terms if t}
        self.text = _norm(" ".join(text_parts))

    @property
    def is_empty(self) -> bool:
        return len(self.vectors) == 0


def job_text_for_embedding(title: str, requirements: dict, description: str) -> str:
    """What we embed for a job.

    The extracted title/responsibilities/skills, not the raw posting: job pages
    are padded with benefits, legal boilerplate and culture copy that drags the
    vector away from what the role actually is.
    """
    parts = [title]
    parts += requirements.get("responsibilities", [])
    parts += requirements.get("required_skills", [])
    parts += requirements.get("preferred_skills", [])
    focused = ". ".join(p for p in parts if p)
    # If extraction gave us nothing, fall back to the top of the description.
    return focused if len(focused) > len(title) + 20 else f"{title}. {description[:1000]}"


def score(
    job,
    requirements: dict,
    job_vector: list[float],
    candidate: CandidateIndex,
    preferences=None,
) -> dict:
    """Compute the four features, the weighted score, and the explanation."""
    required = requirements.get("required_skills", [])
    preferred = requirements.get("preferred_skills", [])
    confidence = float(requirements.get("confidence", 0.0))

    req_matched, req_missing = _split_skills(required, candidate)
    pref_matched, pref_missing = _split_skills(preferred, candidate)

    features = {
        "required_coverage": _ratio(len(req_matched), len(required)),
        "semantic": _semantic(job_vector, candidate),
        "preferred_coverage": _ratio(len(pref_matched), len(preferred)),
        "keyword_overlap": _keyword_overlap(job.title, job.description, candidate),
        "preference_fit": preference_fit(job, preferences),
    }
    total = sum(WEIGHTS[name] * value for name, value in features.items())

    filtered, reason = _hard_filter(job, requirements, confidence, preferences)

    return {
        "score": round(total, 4),
        "features": {k: round(v, 4) for k, v in features.items()},
        "confidence": confidence,
        "hard_filtered": filtered,
        "filter_reason": reason,
        "tier": "full",
        "why": {
            "weights": WEIGHTS,
            "contributions": {
                k: round(WEIGHTS[k] * v, 4) for k, v in features.items()
            },
            "required_matched": req_matched,
            "required_missing": req_missing,
            "preferred_matched": pref_matched,
            "seniority": requirements.get("seniority", ""),
            "min_years": requirements.get("min_years", 0),
        },
    }


def score_cheap(job, job_vector: list[float], candidate: CandidateIndex, preferences=None) -> dict:
    """Rank a job WITHOUT calling the LLM.

    At a few thousand jobs, spending ~25s each on extraction is impossible, so
    the pipeline ranks everything with the two features that need no LLM
    (semantic similarity and keyword overlap) and spends the expensive tier only
    on the best candidates.

    The score is renormalised over the features we actually have, so it stays an
    honest estimate on the same 0-1 scale rather than being dragged down by two
    unknown terms. The UI labels it "estimated" so it is never confused with a
    fully-extracted score.
    """
    # preference_fit is deterministic, so the cheap tier gets it too — three of
    # the five features need no LLM at all.
    features = {
        "semantic": _semantic(job_vector, candidate),
        "keyword_overlap": _keyword_overlap(job.title, job.description, candidate),
        "preference_fit": preference_fit(job, preferences),
    }
    available = sum(WEIGHTS[name] for name in features)
    total = sum(WEIGHTS[name] * value for name, value in features.items()) / available

    filtered, reason = _hard_filter(job, {}, 0.0, preferences)
    return {
        "score": round(total, 4),
        "features": {k: round(v, 4) for k, v in features.items()},
        "confidence": 0.0,  # no extraction yet
        "hard_filtered": filtered,
        "filter_reason": reason,
        "tier": "estimated",
        "why": {
            "weights": {k: round(WEIGHTS[k] / available, 3) for k in features},
            "contributions": {
                k: round(WEIGHTS[k] * v / available, 4) for k, v in features.items()
            },
            "note": "Estimated fit — required-skill coverage not yet extracted.",
        },
    }


def _hard_filter(
    job, requirements: dict, confidence: float, preferences=None
) -> tuple[bool, str]:
    """Knock out roles the candidate cannot or does not want to apply to.

    Title-based rules are deterministic and always apply. Extraction-derived
    rules only fire when the extraction is trustworthy — a bad parse must never
    hide a good job.
    """
    # A pasted job is already a decision. The filter exists to make thousands of
    # scraped postings manageable — it throws away 98% of them — and applying it
    # to the handful someone typed in by hand only ever contradicts them. It also
    # fails in a way that reads as a bug: the job is scored, the score is good,
    # and it silently never reaches the list they went looking for it in.
    if getattr(job, "source", "") == "manual":
        return False, ""

    max_years = getattr(preferences, "max_years", None) or DEFAULT_MAX_YEARS
    allowed = set(getattr(preferences, "allowed_seniority", None) or DEFAULT_ALLOWED_SENIORITY)
    families = set(getattr(preferences, "role_families", None) or DEFAULT_ROLE_FAMILIES)

    family = classify(job.title)
    if family not in families:
        return True, f"not a target role ({family})"
    if not is_fresher_friendly(job.title):
        return True, "senior title"

    # Years come from two independent readings, and we take the stricter one:
    #   * the description itself, via regex — available for EVERY job, including
    #     ones the expensive tier never reaches. This is what stops senior roles
    #     appearing at the top of a fresher's list.
    #   * the LLM extraction, when it exists and is trustworthy.
    # Silence is not a rejection: a posting that states no years returns None and
    # is judged on its title, because most genuine fresher postings say nothing.
    stated = required_years(getattr(job, "description", "") or "")
    extracted = (
        int(requirements.get("min_years", 0) or 0) if confidence >= TRUST_THRESHOLD else 0
    )
    years = max(stated or 0, extracted)
    if years > max_years:
        return True, f"requires {years}+ years"

    if confidence >= TRUST_THRESHOLD:
        # The extracted seniority label is a fuzzy model judgment; years and the
        # title are concrete. So a label of "mid" only filters when the years
        # agree — otherwise "Software Engineer, Android" asking for 1 year gets
        # dropped purely because the model felt it was mid-level. Senior and lead
        # are unambiguous enough to filter on their own.
        seniority = requirements.get("seniority")
        if seniority in OUT_OF_REACH_LEVELS and seniority not in allowed:
            return True, f"{seniority}-level role"
    return False, ""


def location_terms(preferred: list[str] | None) -> list[str]:
    """Every spelling of every place the candidate asked for, lowercase.

    A preference of "Bangalore" has to match a posting that says "Bengaluru".
    They are the same city and the board picked the spelling, not the candidate,
    so resolving through the alias list is the difference between a preference
    that works and one that silently ranks nothing.

    Anything the list has never heard of is kept as typed rather than dropped:
    someone in a city we do not carry should still get their own preference.
    """
    terms: list[str] = []
    for raw in preferred or []:
        text = " ".join(str(raw).lower().split())
        if not text:
            continue
        city = resolve_city(text)
        terms.extend(city.terms if city else [text])
    return terms


def _names_place(location: str, terms: list[str]) -> bool:
    """Whether the location text names one of these places, as a whole word.

    Whole words, not substrings. A plain `in` test read "NY" out of "Kenya" and
    "Sydney, NSW", so a preference could be satisfied by a city on the other side
    of the world that happened to share four letters.
    """
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", location)
        for term in terms
    )


def preference_fit(job, preferences=None) -> float:
    """How well this job matches where the candidate actually wants to work.

    A *soft* signal, not a filter: a great role in the wrong city is still worth
    seeing, it just should not outrank an equally good one in the right city.
    Neutral (0.5) when no preference is expressed, so this feature never
    penalises someone who has not filled the settings in.
    """
    wanted = location_terms(getattr(preferences, "preferred_locations", None))
    remote_ok = getattr(preferences, "remote_ok", True)
    location = (job.location or "").lower()

    if job.remote or "remote" in location:
        return 1.0 if remote_ok else 0.3
    if not wanted:
        return 0.5  # no stated preference — stay neutral
    if _names_place(location, wanted):
        return 1.0
    return 0.4  # in scope (it passed the India filter) but not a preferred city


def _semantic(job_vector: list[float], candidate: CandidateIndex) -> float:
    """Mean cosine similarity of the top-k most relevant KB chunks."""
    if candidate.is_empty or not job_vector:
        return 0.0
    # Vectors are L2-normalised, so the dot product IS the cosine similarity.
    sims = candidate.vectors @ np.array(job_vector, dtype=np.float32)
    top = np.sort(sims)[-TOP_K:]
    return float(np.clip(top.mean(), 0.0, 1.0))


def _keyword_overlap(title: str, description: str, candidate: CandidateIndex) -> float:
    """Share of the posting's distinctive words that appear in the KB.

    Catches domain vocabulary the skill extractor missed ("fintech",
    "recommendation systems") without needing another model.
    """
    words = _tokens(f"{title} {description[:3000]}")
    if not words:
        return 0.0
    hits = sum(1 for w in words if _in_candidate(w, candidate))
    return hits / len(words)


def _split_skills(skills: list[str], candidate: CandidateIndex) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for skill in skills:
        (matched if _in_candidate(_norm(skill), candidate) else missing).append(skill)
    return matched, missing


def _in_candidate(term: str, candidate: CandidateIndex) -> bool:
    """Is this skill/word evidenced anywhere in the candidate's KB?"""
    if not term:
        return False
    term = _ALIASES.get(term, term)
    if term in candidate.terms:
        return True
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", candidate.text) is not None


def _tokens(text: str) -> set[str]:
    """Distinctive words: alphabetic, 3+ chars, not boilerplate."""
    words = re.findall(r"[a-z][a-z0-9+#.]{2,}", _norm(text))
    return {w for w in words if w not in _STOPWORDS}


def _norm(text: str) -> str:
    """Lowercase and strip punctuation, keeping +/# so c++ and c# survive.

    Whitespace runs collapse to one space so multi-word skills match regardless
    of how the source spaced or wrapped them.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]+", " ", (text or "").lower())).strip()


def _ratio(part: int, whole: int) -> float:
    """No requirements listed is not the same as failing them — treat as neutral."""
    return part / whole if whole else 0.0


def embed_job(title: str, requirements: dict, description: str) -> list[float]:
    """The job is the *query* against KB passages, so use the query encoder."""
    return embed_query(job_text_for_embedding(title, requirements, description))
