"""Can someone in *your* region actually apply to this job?

Boards rarely name a country — they write "San Francisco, CA" or "Bengaluru,
Karnataka". So relevance is decided by recognising place names, and the model is
deliberately inverted from the obvious one:

    every region lists its OWN places; every other region's places are foreign.

Adding a new region is therefore one list, not a list plus edits to a global
"reject everything else" list. The rules, in order:

1. A job that names your region is relevant — even if it also names others, so a
   "Remote, Canada; Remote, India" posting still counts for India.
2. A job that names a different region is not.
3. Anything left is relevant only if it is remote. If we cannot tell where a
   non-remote job is, it is not worth showing.

We filter at ingestion rather than at query time: storing thousands of
inapplicable roles would bloat the database and dilute every ranking downstream.
No ML, no LLM — just inspectable lists.
"""
import re

from app.ingestion.cities import terms_for_region

DEFAULT_REGION = "india"


def _compile(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# Each region: a label, and the regexes for forms that need word boundaries
# (country codes, "City, ST").
#
# The `terms` are not written here. They are built from app/ingestion/cities.py,
# which holds every place name in the app along with the other spellings each one
# goes by. This list and the settings dropdown used to be separate, and the way
# that failed was quiet: a city you could pick but that ingestion had never heard
# of looks like it works and ranks nothing.
REGIONS: dict[str, dict] = {
    "india": {
        "label": "India",
        # "IND" as a whole word ("Bangalore, IND"). Not "IN" — that collides
        # with the English word "in", and with Indiana.
        "patterns": _compile(r"\bind\b"),
    },
    "us": {
        "label": "United States",
        "patterns": _compile(
            r"\bu\.?s\.?a?\b",
            # "City, ST" is how boards write US locations. Requiring the comma
            # avoids "OR" (Oregon) matching the word "or", and "IN" (Indiana)
            # matching "in" — or India.
            r",\s*(?:CA|NY|WA|TX|MA|IL|CO|GA|NC|VA|OR|UT|AZ|FL|PA|OH|MI|MN|NJ|MD|NV|TN|SC|MO|WI|CT|DC)\b",
        ),
    },
    "uk": {
        "label": "United Kingdom",
        "patterns": _compile(r"\bu\.?k\.?\b"),
    },
    "eu": {
        "label": "Europe",
        "patterns": _compile(r"\beu\b"),
    },
    "canada": {"label": "Canada", "patterns": []},
    "australia": {"label": "Australia / NZ", "patterns": []},
    "singapore": {"label": "Singapore", "patterns": []},
    "global": {"label": "Anywhere (no location filter)", "patterns": []},
}

for _region, _profile in REGIONS.items():
    _profile["terms"] = terms_for_region(_region)

REGION_IDS = tuple(REGIONS)


def _mentions(text: str, region: str) -> bool:
    profile = REGIONS.get(region)
    if not profile:
        return False
    if any(term in text for term in profile["terms"]):
        return True
    return any(pattern.search(text) for pattern in profile["patterns"])


def is_relevant(
    location: str, remote: bool, title: str = "", region: str = DEFAULT_REGION
) -> bool:
    """True if a candidate based in `region` could realistically apply."""
    if region == "global":
        return True

    loc = (location or "").lower()
    # The title matters as much as the location: "Account Executive, US East"
    # posted as plain "Remote" is not applicable from India.
    text = f"{loc} {(title or '').lower()}"

    if _mentions(text, region):
        return True
    if any(other != region and _mentions(text, other) for other in REGIONS):
        return False

    # Nowhere identifiable: only worth showing if it is remote.
    return remote or "remote" in loc or "anywhere" in loc or not loc
