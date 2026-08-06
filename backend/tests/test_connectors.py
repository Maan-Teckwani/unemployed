"""The two connectors added for coverage, against the shapes the real APIs return.

Fixtures are trimmed copies of live responses, not invented ones. Every field
mapped here was checked against nvidia.wd5 and hygraph.recruitee at the time of
writing, because the failure mode for a connector is not an exception, it is
returning nothing and looking like the company is not hiring.
"""
import httpx
import pytest

from app.connectors import recruitee, workday

# --- Workday -----------------------------------------------------------------
# The listing carries no description and its `locationsText` frequently reads
# "4 Locations", so the location for the pre-filter comes out of externalPath.

WORKDAY_LIST = {
    "total": 3,
    "jobPostings": [
        {
            "title": "Senior Software Engineer, Fabric Networking",
            "externalPath": "/job/India-Bengaluru/Senior-Software-Engineer_JR2020447",
            "locationsText": "4 Locations",
            "postedOn": "Posted Today",
            "bulletFields": ["JR2020447"],
        },
        {
            "title": "Senior System Software Engineer, CPU Platform",
            "externalPath": "/job/Taiwan-Taipei/Senior-System-Software-Engineer_JR2021364",
            "locationsText": "Taipei",
            "postedOn": "Posted Today",
            "bulletFields": ["JR2021364"],
        },
    ],
}

WORKDAY_DETAIL = {
    "jobPostingInfo": {
        "title": "Senior Software Engineer, Fabric Networking",
        "jobDescription": "<p>Build <b>networking</b> software.</p>",
        "location": "India, Bengaluru",
        "startDate": "2026-07-07",
        "jobReqId": "JR2020447",
        "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/Site/job/India-Bengaluru/x_JR2020447",
    }
}

TOKEN = "nvidia.wd5/nvidia/NVIDIAExternalCareerSite"


@pytest.fixture()
def workday_api(monkeypatch):
    """Stand in for the two endpoints, and record what was asked of them."""
    calls = {"list": [], "detail": []}

    class Resp:
        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._p

    def post(url, json=None, timeout=None, follow_redirects=None, headers=None):
        calls["list"].append(json)
        page = (json or {}).get("offset", 0)
        return Resp(WORKDAY_LIST if page == 0 else {"total": 3, "jobPostings": []})

    def get(url, timeout=None, follow_redirects=None, headers=None):
        calls["detail"].append(url)
        return Resp(WORKDAY_DETAIL)

    monkeypatch.setattr(workday.httpx, "post", post)
    monkeypatch.setattr(workday.httpx, "get", get)
    return calls


def test_workday_reads_a_board(workday_api) -> None:
    jobs = workday.fetch(TOKEN, "NVIDIA", "india")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "workday"
    assert job.external_id == "JR2020447"
    assert job.location == "India, Bengaluru"
    # strip_html puts a space where each tag was, which is shared behaviour.
    assert "networking" in job.description and "<" not in job.description
    assert job.apply_url.endswith("x_JR2020447")
    assert job.posted_at.year == 2026


def test_the_location_comes_out_of_the_path_before_paying_for_a_detail(workday_api) -> None:
    """`locationsText` says "4 Locations" for the job we want and "Taipei" for
    the one we do not. Filtering on it drops every multi-site posting, which on
    a real board is most of them."""
    workday.fetch(TOKEN, "NVIDIA", "india")
    assert len(workday_api["detail"]) == 1, "fetched a description for a foreign posting"
    assert "India-Bengaluru" in workday_api["detail"][0]


def test_the_region_is_pushed_to_the_server(workday_api) -> None:
    """A board with two thousand postings pages twenty at a time. Without this
    a single company is a hundred requests before the first description."""
    workday.fetch(TOKEN, "NVIDIA", "india")
    assert workday_api["list"][0]["searchText"] == "India"


def test_a_region_with_no_useful_search_term_pages_instead(workday_api) -> None:
    """"Anywhere" is not a place, and searching for it finds nothing."""
    workday.fetch(TOKEN, "NVIDIA", "global")
    assert workday_api["list"][0]["searchText"] == ""


def test_paging_stops_on_a_short_page(workday_api) -> None:
    workday.fetch(TOKEN, "NVIDIA", "india")
    assert len(workday_api["list"]) == 1


@pytest.mark.parametrize(
    "token",
    ["nvidia", "nvidia.wd5", "nvidia.wd5/nvidia", "https://nvidia.wd5.myworkdayjobs.com"],
)
def test_a_malformed_token_says_so(token: str) -> None:
    """The token carries four parts that cannot be derived from a company name.
    Getting it wrong must be loud, because the quiet version is a board that
    looks empty."""
    with pytest.raises(ValueError, match="sub.dc/tenant/site"):
        workday.fetch(token, "NVIDIA", "india")


def test_a_failed_detail_does_not_lose_the_board(monkeypatch) -> None:
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return WORKDAY_LIST

    monkeypatch.setattr(
        workday.httpx, "post", lambda *a, **kw: Resp() if kw.get("json", {}).get("offset", 0) == 0 else _empty()
    )
    monkeypatch.setattr(
        workday.httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(httpx.ReadTimeout("slow"))
    )
    jobs = workday.fetch(TOKEN, "NVIDIA", "india")
    # The posting still comes through, on the location the path gave us.
    assert [j.location for j in jobs] == ["India, Bengaluru"]
    assert jobs[0].description == ""


def test_a_huge_board_is_capped_rather_than_fetched_forever(monkeypatch) -> None:
    """Descriptions cost a request each, so a board with hundreds of matching
    roles would otherwise be hundreds of round trips against someone else's
    API in the middle of a fetch. The cap is a real limit and worth knowing
    about: past it, a board is silently truncated."""
    many = {
        "total": 500,
        "jobPostings": [
            {
                "title": f"Engineer {i}",
                "externalPath": f"/job/India-Bengaluru/Engineer-{i}_JR{i}",
                "locationsText": "Bengaluru",
                "bulletFields": [f"JR{i}"],
            }
            for i in range(workday.PAGE_SIZE)
        ],
    }
    details = []

    class Resp:
        def __init__(self, p):
            self._p = p

        def raise_for_status(self):
            return None

        def json(self):
            return self._p

    monkeypatch.setattr(workday.httpx, "post", lambda *a, **kw: Resp(many))
    monkeypatch.setattr(
        workday.httpx,
        "get",
        lambda url, **kw: (details.append(url), Resp(WORKDAY_DETAIL))[1],
    )

    jobs = workday.fetch(TOKEN, "NVIDIA", "india")
    assert len(jobs) == workday.MAX_DETAIL_FETCHES
    assert len(details) == workday.MAX_DETAIL_FETCHES


def _empty():
    class R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"total": 3, "jobPostings": []}

    return R()


# --- Recruitee ---------------------------------------------------------------

RECRUITEE = {
    "offers": [
        {
            "id": 2700825,
            "title": "Senior Fullstack Engineer",
            "description": "<p>How you will make an impact</p>",
            "requirements": "<p>5+ years of <b>TypeScript</b></p>",
            "location": "Berlin, Berlin, Germany",
            "city": "Berlin",
            "country_code": "DE",
            "careers_url": "https://jobs.hygraph.com/o/senior-fullstack",
            "careers_apply_url": "https://jobs.hygraph.com/o/senior-fullstack/c/new",
            "remote": True,
            "published_at": "2026-08-05 10:10:39 UTC",
            "company_name": "Hygraph",
        }
    ]
}


@pytest.fixture()
def recruitee_api(monkeypatch):
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return RECRUITEE

    monkeypatch.setattr(recruitee.httpx, "get", lambda *a, **kw: Resp())


def test_recruitee_reads_a_board(recruitee_api) -> None:
    jobs = recruitee.fetch("hygraph", "Hygraph", "global")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "recruitee"
    assert job.external_id == "2700825"
    assert job.company == "Hygraph"
    assert job.remote is True
    assert job.apply_url.endswith("/c/new")


def test_the_requirements_half_is_not_dropped(recruitee_api) -> None:
    """Recruitee splits a posting in two and the second half is the one that
    says which skills are needed. Reading only `description` looks like it
    works and scores every Recruitee job as asking for nothing."""
    job = recruitee.fetch("hygraph", "Hygraph", "global")[0]
    assert "TypeScript" in job.description
    assert "How you will make an impact" in job.description


def test_a_non_iso_timestamp_is_still_a_date(recruitee_api) -> None:
    """Recruitee writes "2026-08-05 10:10:39 UTC", which fromisoformat refuses."""
    job = recruitee.fetch("hygraph", "Hygraph", "global")[0]
    assert (job.posted_at.year, job.posted_at.month, job.posted_at.day) == (2026, 8, 5)


def test_a_missing_location_falls_back_to_city_and_country(monkeypatch) -> None:
    payload = {"offers": [dict(RECRUITEE["offers"][0], location=None)]}

    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    monkeypatch.setattr(recruitee.httpx, "get", lambda *a, **kw: Resp())
    assert recruitee.fetch("hygraph", "Hygraph", "global")[0].location == "Berlin, DE"
