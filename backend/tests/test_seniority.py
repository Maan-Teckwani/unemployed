"""This filter decides which jobs are worth an expensive LLM call, so its
false-negatives cost us real opportunities."""
import pytest

from app.ingestion.seniority import is_fresher_friendly


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Clearly open to a fresher
        ("Software Engineer", True),
        ("Backend Engineer", True),
        ("SDE Intern", True),
        ("Software Engineering Intern - Summer 2026", True),
        ("Graduate Engineer Trainee", True),
        ("Junior Data Analyst", True),
        ("Associate Product Manager", True),  # explicit entry-level track
        ("Software Engineer I", True),
        # Clearly senior
        ("Senior Software Engineer", False),
        ("Sr. Backend Engineer", False),
        ("Staff Engineer, Platform", False),
        ("Principal Data Scientist", False),
        ("Engineering Manager", False),
        ("Director of Engineering", False),
        ("Head of Product", False),
        ("Solutions Architect", False),
        ("Software Engineer II", False),
        ("Backend Engineer III", False),
        # "Intermediate" reads junior but means mid-level.
        ("Intermediate Backend Engineer - Analytics", False),
        ("Intermediate Fullstack Engineer - Data Products", False),
        ("Mid-Level Software Engineer", False),
        # Word-boundary traps
        ("Managed Services Engineer", True),  # "Managed" is not "Manager"
        ("Leadership Development Program Analyst", True),  # "Leadership" != "Lead"
    ],
)
def test_is_fresher_friendly(title: str, expected: bool) -> None:
    assert is_fresher_friendly(title) is expected


@pytest.mark.parametrize(
    ("title", "friendly"),
    [
        # Not a staff-level rank: it is the ordinary IC title at Pure Storage,
        # VMware, Nutanix and Oracle, and new grads are hired into it. Read
        # literally it contains "staff", and every one of these was dropped as
        # unambiguously senior.
        ("Member of Technical Staff", True),
        ("Member of Technical Staff, Networking", True),
        ("Member Of Technical Staff - Golang / Java", True),
        ("MTS - Software Development", True),
        # The phrase is removed rather than exempted, so the rest of the title
        # still decides.
        ("Member of Technical Staff, Senior Backend", False),
        ("MTS - Kernel / Storage Systems Architect", False),
        ("Member of Technical Staff, Production Engineering Lead", False),
        # And a real staff-level rank is still a real staff-level rank.
        ("Staff Software Engineer", False),
        ("Senior Staff Engineer", False),
    ],
)
def test_member_of_technical_staff_is_not_a_staff_rank(title, friendly) -> None:
    assert is_fresher_friendly(title) is friendly
