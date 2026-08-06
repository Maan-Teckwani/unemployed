r"""Workday job-board connector.

The one that matters most for India. Almost every large multinational and every
GCC runs its careers site on Workday, and none of them appear on any of the
boards this app read before.

There is no documented public API. Every Workday careers page is a single-page
app talking to a JSON endpoint on the same host, and that endpoint answers
without a key. This is a plain client for it: no browser, no HTML parsing.

Three things make it more work than the other connectors.

**The token carries four parts.** A board lives at
`{sub}.{dc}.myworkdayjobs.com/{site}` and its API at `/wday/cxs/{tenant}/{site}`,
where the data centre (`wd1`, `wd3`, `wd5`, ...) and the tenant are not derivable
from the company name. So the token is written `sub.dc/tenant/site`, for example
`nvidia.wd5/nvidia/NVIDIAExternalCareerSite`.

**Boards are enormous.** NVIDIA lists two thousand postings, and the listing
endpoint pages twenty at a time, so reading one board completely would be a
hundred requests before a single description. The endpoint takes a `searchText`,
so the region is pushed to the server and the paging is capped.

**The listing has no description**, so that costs a request per job, and its
`locationsText` frequently reads "4 Locations" rather than anywhere. Filtering
on that would drop every multi-site posting, so the location is read from the
posting's own path (`/job/India-Bengaluru/...`) for the cheap pre-filter and
replaced by the authoritative one once the detail is fetched.
"""
import re
from datetime import date, datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION, is_relevant

PAGE_SIZE = 20  # what the endpoint returns whatever you ask for
MAX_PAGES = 15  # 300 postings, after the server has already narrowed by region
MAX_DETAIL_FETCHES = 60  # same safety valve as smartrecruiters

# Handed to the endpoint as `searchText` so a two thousand posting board is
# narrowed by Workday instead of by us. Deliberately a plain place name: this is
# a search box, not a filter, and anything cleverer matches on prose. Regions
# with no useful single term are left out and simply page instead.
_SEARCH_TERMS = {
    "india": "India",
    "us": "United States",
    "uk": "United Kingdom",
    "canada": "Canada",
    "australia": "Australia",
    "singapore": "Singapore",
}

_TOKEN_RE = re.compile(r"^(?P<host>[\w.-]+)/(?P<tenant>[\w.-]+)/(?P<site>[\w.-]+)$")


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    base = _base_url(token)
    postings = _list_postings(base, region)

    jobs = []
    for p in postings:
        title = p.get("title", "")
        path = p.get("externalPath") or ""
        # The cheap pre-filter, on a location guessed from the path. A posting
        # that survives it is confirmed against the real location below.
        if not is_relevant(_location_from_path(path), False, title, region):
            continue
        if len(jobs) >= MAX_DETAIL_FETCHES:
            break

        info = _detail(base, path)
        location = info.get("location") or _location_from_path(path)
        remote = "remote" in f"{location} {title}".lower()
        if not is_relevant(location, remote, title, region):
            continue

        jobs.append(
            RawJob(
                source="workday",
                external_id=_external_id(p, info, path),
                company=company,
                title=info.get("title") or title,
                location=location,
                remote=remote,
                description=strip_html(info.get("jobDescription") or ""),
                apply_url=info.get("externalUrl") or _public_url(token, path),
                posted_at=_parse_date(info.get("startDate")),
            )
        )
    return jobs


def _base_url(token: str) -> str:
    match = _TOKEN_RE.match(token.strip())
    if not match:
        raise ValueError(
            f"workday token must look like sub.dc/tenant/site, got {token!r}"
        )
    host, tenant, site = match["host"], match["tenant"], match["site"]
    return f"https://{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"


def _public_url(token: str, path: str) -> str:
    """Where a person applies, as opposed to where the JSON lives."""
    match = _TOKEN_RE.match(token.strip())
    return f"https://{match['host']}.myworkdayjobs.com/{match['site']}{path}"


def _list_postings(base: str, region: str) -> list[dict]:
    """Page through the listing (metadata only, cheap), narrowed by region."""
    out: list[dict] = []
    for page in range(MAX_PAGES):
        resp = httpx.post(
            f"{base}/jobs",
            json={
                "appliedFacets": {},
                "limit": PAGE_SIZE,
                "offset": page * PAGE_SIZE,
                "searchText": _SEARCH_TERMS.get(region, ""),
            },
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={**HEADERS, "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("jobPostings") or []
        out.extend(postings)
        if len(postings) < PAGE_SIZE or len(out) >= (data.get("total") or 0):
            break
    return out


def _detail(base: str, path: str) -> dict:
    """One posting's full record. A missing description is not fatal."""
    try:
        resp = httpx.get(
            f"{base}{path}",
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={**HEADERS, "Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json().get("jobPostingInfo") or {}
    except Exception:  # noqa: BLE001 - one bad posting must not lose the board
        return {}


def _location_from_path(path: str) -> str:
    """`/job/India-Bengaluru/Senior-Engineer_JR123` -> "India, Bengaluru".

    Used only to decide whether a posting is worth a second request. The real
    location comes back with the detail and overwrites this.
    """
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2 or parts[0] != "job":
        return ""
    return parts[1].replace("-", ", ")


def _external_id(posting: dict, info: dict, path: str) -> str:
    """Workday's requisition id, which is stable across re-postings.

    `bulletFields` is where the listing puts it and `jobReqId` is where the
    detail does. The path is the fallback, and is stable enough to dedupe on.
    """
    bullets = posting.get("bulletFields") or []
    return str(info.get("jobReqId") or (bullets[0] if bullets else "") or path)


def _parse_date(value: str | None) -> datetime | None:
    """`startDate` is a plain "2026-08-06". `postedOn` is "Posted Today"."""
    if not value:
        return None
    try:
        return datetime.combine(date.fromisoformat(value.strip()), datetime.min.time())
    except ValueError:
        return None
