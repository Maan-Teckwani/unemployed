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


_URL_RE = re.compile(
    r"https?://(?P<host>[\w-]+\.wd\d+)\.myworkdayjobs\.com/(?P<path>[^?#]*)", re.I
)
# The careers page declares its own API config in an inline script:
#   window.workday = { tenant: "nvidia", siteId: "NVIDIAExternalCareerSite", ... }
# Which is the only reliable source for the tenant, because it is not in the
# public URL and is not always the subdomain: Wells Fargo is `wf`.
_DECLARED = re.compile(
    r"""tenant:\s*["'](?P<tenant>[\w.-]+)["'].*?siteId:\s*["'](?P<site>[\w.-]+)["']""",
    re.S,
)
# Workday serves the SPA shell to browsers and 406s anything that does not look
# like one, so reading that page needs a browser's Accept header.
_PAGE_HEADERS = {**HEADERS, "Accept": "text/html,application/xhtml+xml"}


def resolve(url: str, region: str = DEFAULT_REGION) -> dict | None:
    """Turn a careers link into a verified board token, or None.

    This exists because Workday boards cannot be discovered the way the other
    platforms can. Their API path ends in a site slug chosen per tenant and
    derived from nothing: "External", "External_Careers", "search",
    "Jobsathpe" and "CorporateCareers" are all real. Guessing it found six
    companies in fifty nine, and every extra guess is another request against
    someone else's server.

    A person reads the slug off the careers URL in one look, so they paste that
    instead. The tenant is the part the URL does not carry, and the page
    declares it. Where the page will not serve (Wells Fargo answers 500), the
    subdomain is tried as the tenant, which is right for twelve of the thirteen
    boards seeded so far.

    Nothing is returned unless the board answers and has jobs for this region,
    the same collision guard the rest of discovery applies.
    """
    match = _URL_RE.match(url.strip())
    if not match:
        return None

    host = match["host"].lower()
    segments = [s for s in match["path"].split("/") if s]
    # Trim a language prefix and anything after the site, so a link copied from
    # a job posting works as well as one copied from the board itself.
    if segments and re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?", segments[0]):
        segments.pop(0)
    site_from_url = segments[0] if segments else ""

    declared = _declared_config(f"https://{host}.myworkdayjobs.com/{site_from_url}")
    candidates = []
    if declared:
        candidates.append(declared)
    if site_from_url:
        candidates.append((host.split(".")[0], site_from_url))

    for tenant, site in dict.fromkeys(candidates):
        token = f"{host}/{tenant}/{site}"
        counted = _count_matching(token, region)
        if counted is not None and counted["matched_jobs"] > 0:
            return {"source": "workday", "token": token, **counted}
    return None


def _declared_config(page_url: str) -> tuple[str, str] | None:
    try:
        resp = httpx.get(
            page_url, timeout=TIMEOUT, follow_redirects=True, headers=_PAGE_HEADERS
        )
        if resp.status_code != 200:
            return None
        found = _DECLARED.search(resp.text)
    except Exception:  # noqa: BLE001 - an unreadable page just means we guess
        return None
    return (found["tenant"], found["site"]) if found else None


def _count_matching(token: str, region: str) -> dict | None:
    """Ask the board for one page and count what this region could apply to."""
    try:
        postings = _list_postings(_base_url(token), region)[:PAGE_SIZE]
    except Exception:  # noqa: BLE001 - not a board, or not this token
        return None
    matched = sum(
        1
        for p in postings
        if is_relevant(_location_from_path(p.get("externalPath") or ""), False,
                       p.get("title", ""), region)
    )
    return {"total_jobs": len(postings), "matched_jobs": matched}


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
