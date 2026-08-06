"""Greenhouse job-board connector.

Greenhouse exposes every board as public JSON, so this is a plain API client —
no browser automation, no HTML scraping, and it does not break when the company
restyles its careers page.
"""
from datetime import datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION

# `content=true` returns the full description, so one request covers a whole board.
URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    # `region` is part of the shared connector signature; only sources that
    # must filter mid-fetch (see smartrecruiters) actually use it.
    resp = httpx.get(URL.format(token=token), timeout=TIMEOUT, follow_redirects=True, headers=HEADERS)
    resp.raise_for_status()

    jobs = []
    for j in resp.json().get("jobs", []):
        location = (j.get("location") or {}).get("name", "") or ""
        jobs.append(
            RawJob(
                source="greenhouse",
                external_id=str(j["id"]),
                company=j.get("company_name") or company,
                title=j.get("title", ""),
                location=location,
                remote="remote" in location.lower(),
                description=strip_html(j.get("content", "")),
                apply_url=j.get("absolute_url", ""),
                posted_at=_parse_date(j.get("first_published") or j.get("updated_at")),
            )
        )
    return jobs


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
