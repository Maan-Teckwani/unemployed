"""Ashby job-board connector.

Like Greenhouse and Lever, Ashby publishes each board as JSON and includes the
full description in the listing, so one request covers a whole company.
"""
from datetime import datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION

URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    # `region` is part of the shared connector signature; only sources that
    # must filter mid-fetch (see smartrecruiters) actually use it.
    resp = httpx.get(URL.format(token=token), timeout=TIMEOUT, follow_redirects=True, headers=HEADERS)
    resp.raise_for_status()

    jobs = []
    for j in resp.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        location = j.get("location") or ""
        jobs.append(
            RawJob(
                source="ashby",
                external_id=str(j["id"]),
                company=company,
                title=j.get("title", ""),
                location=location,
                remote=bool(j.get("isRemote")) or "remote" in location.lower(),
                description=j.get("descriptionPlain")
                or strip_html(j.get("descriptionHtml", "")),
                apply_url=j.get("applyUrl") or j.get("jobUrl", ""),
                posted_at=_parse_date(j.get("publishedAt")),
            )
        )
    return jobs


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
