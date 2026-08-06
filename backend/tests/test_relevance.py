"""The India/remote relevance filter is the gate every ingested job passes
through, so its edge cases are worth pinning down."""
import pytest

from app.ingestion.relevance import is_relevant


@pytest.mark.parametrize(
    ("location", "remote", "title", "expected"),
    [
        ("Bangalore, India", False, "SDE Intern", True),
        ("Hyderabad", False, "Backend Engineer", True),
        ("Remote, Bangalore", True, "Senior Backend Engineer", True),
        ("Remote", True, "Software Engineer", True),
        ("", False, "Software Engineer", True),
        # Region lives in the title, not the location.
        ("Remote", True, "Account Executive - Mid-Market, US East", False),
        ("San Francisco, USA", False, "Engineer", False),
        ("London", False, "Engineer", False),
        ("Remote - Canada", True, "Engineer", False),
        # "Customer" must not trip the \bus\b region check.
        ("Pune", False, "Customer Success Manager", True),
        # Multi-region posting that still includes India stays.
        ("Remote, Canada; Remote, India", True, "Backend Engineer", True),
        # Region named in the title only.
        ("", False, "Corporate Solutions Engineer, Nordics", False),
        ("", False, "Enterprise Solutions Engineer, Italy", False),
        # "Indonesia" must not be read as "India".
        ("Jakarta, Indonesia", False, "Engineer", False),
        # --- US locations that never name a country (all real, from the pool) ---
        ("San Francisco, CA", False, "Software Engineer", False),
        ("San Francisco, California", False, "Software Engineer Intern", False),
        ("San Francisco HQ", False, "Software Engineer, Backend", False),
        ("New York, New York", False, "Developer Advocate", False),
        ("New York, NY (HQ)", False, "Mobile Engineer, iOS", False),
        ("Foster City, CA", False, "Software Engineer", False),
        ("North America", True, "Developer Relations", False),
        ("Remote-Friendly (Travel Required) | San Francisco, CA", True, "Red Team Engineer", False),
        # --- India must still win, even alongside a US state pattern ---
        ("Chennai, TN, India", False, "Network System Test Engineer", True),
        ("Bangalore, IND", False, "Software Development Engineer", True),
        ("Remote - India", False, "Associate Application Engineer", True),
        ("Bengaluru, Karnataka, India", False, "SDE Intern - Frontend", True),
        # --- word-boundary traps for two-letter state codes ---
        ("Remote or Hybrid", True, "Software Engineer", True),   # "or" != Oregon
        ("Pune, India", False, "Engineer in Test", True),        # "in" != Indiana
    ],
)
def test_is_relevant(location: str, remote: bool, title: str, expected: bool) -> None:
    assert is_relevant(location, remote, title) is expected


# ---- other regions ----------------------------------------------------------
@pytest.mark.parametrize(
    ("region", "location", "expected"),
    [
        # Each region keeps its own places...
        ("us", "San Francisco, CA", True),
        ("us", "New York, NY (HQ)", True),
        ("uk", "London, England", True),
        ("eu", "Berlin, Germany", True),
        ("canada", "Toronto, Canada", True),
        ("australia", "Sydney, Australia", True),
        # ...and rejects everyone else's.
        ("us", "Bengaluru, Karnataka, India", False),
        ("uk", "San Francisco, CA", False),
        ("eu", "Bangalore, India", False),
        ("india", "Berlin, Germany", False),
    ],
)
def test_regions_keep_their_own_and_reject_others(
    region: str, location: str, expected: bool
) -> None:
    assert is_relevant(location, False, "Software Engineer", region) is expected


def test_global_region_keeps_everything() -> None:
    """"Anywhere" means no geographic filtering at all."""
    for location in ("San Francisco, CA", "Bengaluru, India", "Tokyo, Japan", ""):
        assert is_relevant(location, False, "Software Engineer", "global") is True


def test_remote_is_relevant_everywhere_when_no_region_is_named() -> None:
    for region in ("india", "us", "uk", "eu"):
        assert is_relevant("Remote", True, "Software Engineer", region) is True


def test_unknown_non_remote_location_is_rejected() -> None:
    """If we cannot tell where a desk job is, it is not worth showing."""
    assert is_relevant("Springfield", False, "Software Engineer", "india") is False


@pytest.mark.parametrize(
    "title",
    [
        "Senior System Software Engineer, CPU Platform",  # "la" inside "platform"
        "Java Class Library Maintainer",  # inside "class"
        "Solar Analytics Engineer",  # inside "solar"
        "Flagship Product Engineer",  # inside "flag"
    ],
)
def test_a_place_name_must_be_a_whole_word(title: str) -> None:
    """"la" is a real short form for Los Angeles and a real substring of
    "platform", "class", "solar" and "flag".

    The damage was not wrong jobs on a US list. Naming another region is what
    disqualifies a job, so every posting whose title happened to contain those
    letters vanished from every other region's list. Measured on a real
    database, twelve India jobs were being dropped this way and a hundred and
    twenty six foreign jobs were being counted as American.
    """
    assert is_relevant("Taiwan, Taipei", False, title, "us") is False
    assert is_relevant("Bengaluru, India", False, title, "india") is True


def test_bangalore_is_not_los_angeles() -> None:
    """The substring is right there in the middle of the word."""
    assert is_relevant("Bangalore", False, "Backend Engineer", "us") is False
    assert is_relevant("Bangalore", False, "Backend Engineer", "india") is True


def test_short_forms_still_match_when_they_are_the_whole_word() -> None:
    """The fix must not cost the abbreviations people actually write."""
    assert is_relevant("LA, California", False, "Engineer", "us") is True
    assert is_relevant("BLR", False, "Engineer", "india") is True
    assert is_relevant("Remote - NCR", False, "Engineer", "india") is True
