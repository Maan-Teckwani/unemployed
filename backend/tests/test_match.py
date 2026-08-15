"""The scoring math is the product's core claim ("why 62%?"), so the feature
calculations and the filter rules are pinned down here."""
from types import SimpleNamespace

import numpy as np
import pytest

from app.ai.match import WEIGHTS, CandidateIndex, _hard_filter, _in_candidate, score, score_cheap


def job_stub(
    title: str,
    description: str = "",
    location: str = "Bengaluru, India",
    remote: bool = False,
    source: str = "greenhouse",
):
    """A Job stand-in. Real rows always carry location/remote/source, so the double does too."""
    return SimpleNamespace(
        title=title, description=description, location=location, remote=remote, source=source
    )


def chunk(title: str, accomplishment: str, technologies=(), skills=(), dim: int = 4):
    """A KB chunk stand-in with a fixed, tiny embedding."""
    vec = np.zeros(dim, dtype=np.float32)
    vec[0] = 1.0
    return SimpleNamespace(
        title=title,
        accomplishment=accomplishment,
        impact=None,
        technologies=list(technologies),
        skills=list(skills),
        embedding=vec.tolist(),
    )


@pytest.fixture
def candidate() -> CandidateIndex:
    return CandidateIndex(
        [
            chunk(
                "Chat app",
                "Built a realtime backend serving 200 users",
                technologies=["Python", "FastAPI", "PostgreSQL"],
                skills=["backend"],
            )
        ]
    )


def test_weights_sum_to_one() -> None:
    # If this drifts, every score silently changes meaning.
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("skill", "expected"),
    [
        ("Python", True),
        ("python", True),          # case-insensitive
        ("PostgreSQL", True),
        ("Postgres", True),        # alias -> postgresql
        ("psql", True),            # alias
        ("FastAPI", True),
        ("realtime", True),        # found in accomplishment text
        ("Kubernetes", False),
        ("", False),
    ],
)
def test_skill_presence(candidate: CandidateIndex, skill: str, expected: bool) -> None:
    from app.ai.match import _norm

    assert _in_candidate(_norm(skill), candidate) is expected


def test_score_is_weighted_sum(candidate: CandidateIndex) -> None:
    job = job_stub("Backend Engineer", "Build APIs in Python")
    requirements = {
        "required_skills": ["Python", "Kubernetes"],  # 1 of 2 -> 0.5
        "preferred_skills": [],
        "responsibilities": [],
        "seniority": "entry",
        "min_years": 0,
        "confidence": 0.9,
    }
    # Job vector identical to the chunk vector -> semantic similarity 1.0
    result = score(job, requirements, [1.0, 0.0, 0.0, 0.0], candidate)

    assert result["features"]["required_coverage"] == pytest.approx(0.5)
    assert result["features"]["semantic"] == pytest.approx(1.0)
    expected = sum(WEIGHTS[k] * v for k, v in result["features"].items())
    assert result["score"] == pytest.approx(round(expected, 4))
    assert result["why"]["required_matched"] == ["Python"]
    assert result["why"]["required_missing"] == ["Kubernetes"]


def test_no_requirements_is_neutral_not_perfect(candidate: CandidateIndex) -> None:
    """An empty requirement list must not read as 100% coverage."""
    job = job_stub("Engineer")
    requirements = {
        "required_skills": [],
        "preferred_skills": [],
        "responsibilities": [],
        "seniority": "entry",
        "min_years": 0,
        "confidence": 0.0,
    }
    result = score(job, requirements, [1.0, 0.0, 0.0, 0.0], candidate)
    assert result["features"]["required_coverage"] == 0.0


def test_cheap_tier_renormalises_to_a_comparable_scale(candidate: CandidateIndex) -> None:
    """Tier 1 has no skill-coverage features, so its score must be renormalised.

    Otherwise every un-extracted job would rank below every extracted one purely
    because two of its four weights are missing — and the shortlist that decides
    where to spend LLM time would be meaningless.
    """
    job = job_stub("Backend Engineer", "Build APIs in Python")
    result = score_cheap(job, [1.0, 0.0, 0.0, 0.0], candidate)

    assert result["tier"] == "estimated"
    assert result["confidence"] == 0.0
    # Perfect semantic similarity, so the score must approach 1 rather than 0.30.
    assert result["score"] > 0.6
    assert result["score"] <= 1.0
    # Renormalised weights still sum to 1 across the available features.
    assert sum(result["why"]["weights"].values()) == pytest.approx(1.0, abs=0.01)


def test_cheap_tier_still_applies_hard_filters(candidate: CandidateIndex) -> None:
    """Filtering must not wait for extraction — that is the point of tier 1."""
    job = job_stub("Senior Growth Manager")
    result = score_cheap(job, [1.0, 0.0, 0.0, 0.0], candidate)
    assert result["hard_filtered"] is True


@pytest.mark.parametrize(
    ("title", "seniority", "min_years", "confidence", "filtered"),
    [
        ("Software Engineer", "entry", 0, 0.9, False),
        ("Software Engineer", "entry", 1, 0.9, False),
        # Not a target role family, however junior it is.
        ("Growth StratOps Associate", "entry", 0, 0.9, True),
        ("Recruiting Coordinator", "entry", 0, 0.9, True),
        # "Intermediate" means mid-level -> blocked on the title alone.
        ("Intermediate Backend Engineer", "entry", 0, 0.9, True),
        # A fuzzy "mid" label must NOT override concrete years within budget.
        ("Software Engineer, Android", "mid", 1, 0.7, False),
        # ...but the same label with too many years is filtered on the years.
        ("Software Engineer, Android", "mid", 6, 0.9, True),
        ("Senior Software Engineer", "entry", 0, 0.9, True),   # title rule
        ("Software Engineer", "entry", 5, 0.9, True),          # too many years
        ("Software Engineer", "senior", 0, 0.9, True),         # senior level
        # Untrusted extraction must NOT hide a job.
        ("Software Engineer", "senior", 9, 0.2, False),
    ],
)
def test_hard_filter(
    title: str, seniority: str, min_years: int, confidence: float, filtered: bool
) -> None:
    job = job_stub(title)
    requirements = {"seniority": seniority, "min_years": min_years}
    assert _hard_filter(job, requirements, confidence)[0] is filtered


@pytest.mark.parametrize(
    "title",
    [
        "Innovation intern",            # classifies as "other"
        "Recruiting Coordinator",       # a family the user does not want
        "Senior Software Engineer",     # a title rule
        "Software Engineer",            # would pass anyway
    ],
)
def test_pasted_jobs_are_never_filtered(title: str) -> None:
    """Every rule that filters a scraped job must let a pasted one through.

    Typing a job in by hand is already the decision the filter exists to make,
    and a pasted job that scores well but never reaches the list reads as the
    app losing it.
    """
    job = job_stub(title, source="manual")
    assert _hard_filter(job, {"seniority": "senior", "min_years": 9}, 0.9) == (False, "")


def test_scraped_jobs_are_still_filtered() -> None:
    """The exemption must be about the source, not a hole in the rules."""
    job = job_stub("Innovation intern", source="greenhouse")
    assert _hard_filter(job, {}, 0.0)[0] is True
