"""SmartRecruiters job-board connector.

Different in one important way: the listing endpoint returns metadata only, so
the description costs an extra request *per job*. A board with 143 postings of
which 4 are in India would mean 143 wasted round trips.

So this connector checks location relevance on the cheap listing data first and
only fetches descriptions for the survivors. Connectors normally do not filter —
this one does because the alternative is a pathological request pattern against
someone else's API.
"""
from datetime import datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION, is_relevant

LIST_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
PAGE_SIZE = 100
MAX_DETAIL_FETCHES = 60  # safety valve for very large boards


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    postings = _list_postings(token)

    jobs = []
    for p in postings:
        location = (p.get("location") or {}).get("fullLocation") or ""
        remote = bool((p.get("location") or {}).get("remote"))
        title = p.get("name", "")
        if not is_relevant(location, remote, title, region):
            continue
        if len(jobs) >= MAX_DETAIL_FETCHES:
            break

        jobs.append(
            RawJob(
                source="smartrecruiters",
                external_id=str(p["id"]),
                company=company,
                title=title,
                location=location,
                remote=remote,
                description=_description(token, p["id"]),
                apply_url=f"https://jobs.smartrecruiters.com/{token}/{p['id']}",
                posted_at=_parse_date(p.get("releasedDate")),
            )
        )
    return jobs


def _list_postings(token: str) -> list[dict]:
    """Page through the postings list (metadata only, cheap)."""
    out: list[dict] = []
    offset = 0
    while True:
        resp = httpx.get(
            LIST_URL.format(token=token),
            params={"limit": PAGE_SIZE, "offset": offset},
            timeout=TIMEOUT,
            follow_redirects=True,
            headers=HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        out.extend(content)
        offset += PAGE_SIZE
        if offset >= data.get("totalFound", 0) or not content:
            return out


def _description(token: str, posting_id: str) -> str:
    """Fetch and flatten one posting's ad sections into plain text."""
    try:
        resp = httpx.get(
            f"{LIST_URL.format(token=token)}/{posting_id}",
            timeout=TIMEOUT,
            follow_redirects=True,
            headers=HEADERS,
        )
        resp.raise_for_status()
        sections = ((resp.json().get("jobAd") or {}).get("sections")) or {}
    except Exception:  # noqa: BLE001 - a missing description is not fatal
        return ""

    parts = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text")
        if text:
            parts.append(strip_html(text))
    return "\n\n".join(parts)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
