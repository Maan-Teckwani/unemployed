"""Lever job-board connector.

Same idea as Greenhouse but a different shape: the description is split across
`descriptionPlain` and a `lists` array (requirements, responsibilities), so we
join them back into one document.
"""
from datetime import UTC, datetime

import httpx

from app.connectors.base import HEADERS, TIMEOUT, RawJob, strip_html
from app.ingestion.relevance import DEFAULT_REGION

URL = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch(token: str, company: str, region: str = DEFAULT_REGION) -> list[RawJob]:
    # `region` is part of the shared connector signature; only sources that
    # must filter mid-fetch (see smartrecruiters) actually use it.
    resp = httpx.get(URL.format(token=token), timeout=TIMEOUT, follow_redirects=True, headers=HEADERS)
    resp.raise_for_status()

    jobs = []
    for p in resp.json():
        categories = p.get("categories") or {}
        location = categories.get("location", "") or ""
        workplace = (p.get("workplaceType") or "").lower()
        jobs.append(
            RawJob(
                source="lever",
                external_id=str(p["id"]),
                company=company,
                title=p.get("text", ""),
                location=location,
                remote=workplace == "remote" or "remote" in location.lower(),
                description=_description(p),
                apply_url=p.get("hostedUrl") or p.get("applyUrl", ""),
                posted_at=_parse_epoch_ms(p.get("createdAt")),
            )
        )
    return jobs


def _description(p: dict) -> str:
    """Join the description with its bullet lists into one plain-text document."""
    parts = [p.get("descriptionPlain") or strip_html(p.get("description", ""))]
    for section in p.get("lists") or []:
        parts.append(section.get("text", ""))
        parts.append(strip_html(section.get("content", "")))
    parts.append(p.get("additionalPlain") or "")
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _parse_epoch_ms(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None
