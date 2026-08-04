"""The places this app knows by name, and the other names they go by.

There is exactly one list of place names in the codebase and this is it.
`relevance.py` builds its region matcher from it, the settings dropdown is served
from it, and `match.preference_fit` resolves what the user picked through it.
Two lists would drift, and the way they would drift is silent: a city offered in
the dropdown that the ingestion filter has never heard of looks like it works and
quietly ranks nothing.

Aliases are the point of the file. Boards write whatever the company typed, so
the same place arrives as "Bengaluru" and "Bangalore", "Gurgaon" and "Gurugram",
"NYC" and "New York". Someone who types the name they grew up with should not
silently get worse rankings than someone who typed the name the company used.

Region terms are the things that are not cities: country names, a few states and
the wider groupings. They identify a region but nobody should be offered
"EMEA" as their preferred location, so they are kept apart from the cities.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class City:
    """One place, under every name it is written as."""

    id: str
    """Stable key. Lowercase, what gets stored."""

    label: str
    """What the reader sees."""

    region: str
    """Which region in REGIONS this sits in."""

    aliases: tuple[str, ...] = field(default=())
    """Other spellings, lowercase. The label is always matched too."""

    @property
    def terms(self) -> tuple[str, ...]:
        """Every string this city is recognised by, lowercase."""
        return (self.label.lower(), *self.aliases)


CITIES: tuple[City, ...] = (
    # India
    City("bengaluru", "Bengaluru", "india", ("bangalore", "blr")),
    City("mumbai", "Mumbai", "india", ("bombay",)),
    City("delhi", "Delhi", "india", ("new delhi", "ncr")),
    City("gurugram", "Gurugram", "india", ("gurgaon",)),
    City("noida", "Noida", "india"),
    City("hyderabad", "Hyderabad", "india", ("hyd",)),
    City("pune", "Pune", "india"),
    City("chennai", "Chennai", "india", ("madras",)),
    City("kolkata", "Kolkata", "india", ("calcutta",)),
    City("ahmedabad", "Ahmedabad", "india"),
    City("jaipur", "Jaipur", "india"),
    City("indore", "Indore", "india"),
    City("kochi", "Kochi", "india", ("cochin", "ernakulam")),
    City("coimbatore", "Coimbatore", "india"),
    City("chandigarh", "Chandigarh", "india"),
    City("thiruvananthapuram", "Thiruvananthapuram", "india", ("trivandrum",)),
    City("mysuru", "Mysuru", "india", ("mysore",)),
    City("nagpur", "Nagpur", "india"),
    City("vadodara", "Vadodara", "india", ("baroda",)),
    City("surat", "Surat", "india"),
    City("bhubaneswar", "Bhubaneswar", "india"),
    City("visakhapatnam", "Visakhapatnam", "india", ("vizag",)),
    # United States
    City("san-francisco", "San Francisco", "us", ("sf", "bay area")),
    City("new-york", "New York", "us", ("nyc", "new york city", "manhattan", "brooklyn")),
    City("seattle", "Seattle", "us"),
    City("foster-city", "Foster City", "us"),
    City("palo-alto", "Palo Alto", "us"),
    City("mountain-view", "Mountain View", "us"),
    City("menlo-park", "Menlo Park", "us"),
    City("santa-clara", "Santa Clara", "us"),
    City("sunnyvale", "Sunnyvale", "us"),
    City("san-jose", "San Jose", "us"),
    City("los-angeles", "Los Angeles", "us", ("la",)),
    City("san-diego", "San Diego", "us"),
    City("austin", "Austin", "us"),
    City("boston", "Boston", "us"),
    City("chicago", "Chicago", "us"),
    City("denver", "Denver", "us"),
    City("boulder", "Boulder", "us"),
    City("atlanta", "Atlanta", "us"),
    City("dallas", "Dallas", "us"),
    City("houston", "Houston", "us"),
    City("miami", "Miami", "us"),
    City("philadelphia", "Philadelphia", "us", ("philly",)),
    City("phoenix", "Phoenix", "us"),
    City("portland", "Portland", "us"),
    City("salt-lake-city", "Salt Lake City", "us"),
    City("nashville", "Nashville", "us"),
    City("charlotte", "Charlotte", "us"),
    City("raleigh", "Raleigh", "us"),
    City("pittsburgh", "Pittsburgh", "us"),
    City("detroit", "Detroit", "us"),
    City("minneapolis", "Minneapolis", "us"),
    City("ann-arbor", "Ann Arbor", "us"),
    City("redmond", "Redmond", "us"),
    City("bellevue", "Bellevue", "us"),
    City("washington", "Washington", "us", ("washington dc", "washington, d.c.")),
    # United Kingdom
    City("london", "London", "uk"),
    City("manchester", "Manchester", "uk"),
    City("birmingham", "Birmingham", "uk"),
    City("edinburgh", "Edinburgh", "uk"),
    City("glasgow", "Glasgow", "uk"),
    City("bristol", "Bristol", "uk"),
    City("leeds", "Leeds", "uk"),
    City("cambridge", "Cambridge", "uk"),
    City("oxford", "Oxford", "uk"),
    City("belfast", "Belfast", "uk"),
    # Europe
    City("berlin", "Berlin", "eu"),
    City("munich", "Munich", "eu", ("muenchen", "munchen")),
    City("hamburg", "Hamburg", "eu"),
    City("paris", "Paris", "eu"),
    City("amsterdam", "Amsterdam", "eu"),
    City("madrid", "Madrid", "eu"),
    City("barcelona", "Barcelona", "eu"),
    City("milan", "Milan", "eu", ("milano",)),
    City("rome", "Rome", "eu", ("roma",)),
    City("warsaw", "Warsaw", "eu", ("warszawa",)),
    City("krakow", "Krakow", "eu", ("cracow",)),
    City("dublin", "Dublin", "eu"),
    City("stockholm", "Stockholm", "eu"),
    City("oslo", "Oslo", "eu"),
    City("copenhagen", "Copenhagen", "eu"),
    City("helsinki", "Helsinki", "eu"),
    City("zurich", "Zurich", "eu", ("zuerich",)),
    City("vienna", "Vienna", "eu", ("wien",)),
    City("brussels", "Brussels", "eu"),
    City("lisbon", "Lisbon", "eu", ("lisboa",)),
    City("prague", "Prague", "eu", ("praha",)),
    City("bucharest", "Bucharest", "eu"),
    City("budapest", "Budapest", "eu"),
    City("athens", "Athens", "eu"),
    # Canada
    City("toronto", "Toronto", "canada"),
    City("vancouver", "Vancouver", "canada"),
    City("montreal", "Montreal", "canada"),
    City("ottawa", "Ottawa", "canada"),
    City("calgary", "Calgary", "canada"),
    City("waterloo", "Waterloo", "canada"),
    # Australia and New Zealand
    City("sydney", "Sydney", "australia"),
    City("melbourne", "Melbourne", "australia"),
    City("brisbane", "Brisbane", "australia"),
    City("perth", "Perth", "australia"),
    City("canberra", "Canberra", "australia"),
    City("auckland", "Auckland", "australia"),
    City("wellington", "Wellington", "australia"),
    # Singapore
    City("singapore", "Singapore", "singapore"),
)


# Not cities: countries, a couple of US states, and the groupings boards use.
# They tell you which region a posting is in, which is why relevance.py needs
# them, but "EMEA" is not somewhere a person lives so the dropdown never shows
# them.
REGION_TERMS: dict[str, tuple[str, ...]] = {
    "india": ("india",),
    "us": ("united states", "usa", "u.s.", "north america", "americas", "california", "texas"),
    "uk": ("united kingdom", "england", "scotland", "wales"),
    "eu": (
        "europe", "emea", "germany", "france", "netherlands", "spain", "italy",
        "poland", "ireland", "sweden", "norway", "denmark", "finland",
        "switzerland", "austria", "belgium", "portugal", "czech", "romania",
        "hungary", "nordics", "greece",
    ),
    "canada": ("canada",),
    "australia": ("australia", "new zealand"),
    "singapore": (),
    "global": (),
}


def cities_in(region: str) -> tuple[City, ...]:
    """The cities of one region, or all of them for `global`."""
    if region == "global":
        return CITIES
    return tuple(c for c in CITIES if c.region == region)


def terms_for_region(region: str) -> tuple[str, ...]:
    """Every lowercase string that identifies this region, cities included.

    This is what relevance.py matches postings against. Built here so that
    adding a city to the list above also teaches the ingestion filter about it,
    rather than needing the same edit in two files.
    """
    city_terms = tuple(term for c in CITIES if c.region == region for term in c.terms)
    return REGION_TERMS.get(region, ()) + city_terms


# Every name any city goes by, mapped to that city. Built once.
_BY_TERM: dict[str, City] = {term: c for c in CITIES for term in c.terms}
_BY_ID: dict[str, City] = {c.id: c for c in CITIES}


def resolve(text: str) -> City | None:
    """The city this text names, under any of its spellings, or None.

    Used on the way in, so that a preference saved as "bangalore" and one saved
    as "Bengaluru" are the same preference.
    """
    key = " ".join((text or "").lower().split())
    if not key:
        return None
    return _BY_ID.get(key) or _BY_TERM.get(key)
