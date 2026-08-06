"""Recruitee job-board connector.

The simplest of the lot: one public request returns every posting with its full
text, so there is no paging and no second round trip.

The one wrinkle is that Recruitee splits a posting in two. `description` is the
pitch and `requirements` is the part that says which skills are needed, and the
second one is the half this app actually matches against. Reading only
`description` looks like it works and quietly scores every Recruitee job as
though it asked for nothing.
"""
from datetime import UTC, datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION

URL = "https://{token}.recruitee.com/api/offers/"


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    # `region` is part of the shared connector signature; filtering happens in
    # the pipeline, because one request already brought back everything.
    resp = httpx.get(
        URL.format(token=token), timeout=TIMEOUT, follow_redirects=True, headers=HEADERS
    )
    resp.raise_for_status()

    jobs = []
    for o in resp.json().get("offers", []):
        location = o.get("location") or ", ".join(
            part for part in (o.get("city"), o.get("country_code")) if part
        )
        jobs.append(
            RawJob(
                source="recruitee",
                external_id=str(o["id"]),
                company=o.get("company_name") or company,
                title=o.get("title", ""),
                location=location,
                remote=bool(o.get("remote")),
                description=_text(o),
                apply_url=o.get("careers_apply_url") or o.get("careers_url") or "",
                posted_at=_parse_date(o.get("published_at")),
            )
        )
    return jobs


def _text(offer: dict) -> str:
    parts = [strip_html(offer.get(key) or "") for key in ("description", "requirements")]
    return "\n\n".join(part for part in parts if part)


def _parse_date(value: str | None) -> datetime | None:
    """Recruitee writes "2026-08-05 10:10:39 UTC", which is not ISO 8601."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=UTC)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
