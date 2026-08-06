"""Shared connector contract: every source produces the same `RawJob` shape.

A connector's only job is *fetch + map to RawJob*. It does not touch the
database, filter, or dedupe — that keeps each connector small, independently
testable, and safe to fail on its own.
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime

# Connectors get their own timeout: a slow board should fail fast, not hang the run.
TIMEOUT = 30.0

# Who is knocking. These are public endpoints belonging to other people, and
# the run now reads eight of them at once, so it should be possible to tell
# what this traffic is and where to complain about it from the logs alone.
HEADERS = {
    "User-Agent": (
        "unemployed/1.0 (+https://github.com/Maan-Teckwani/unemployed) "
        "local job search assistant"
    )
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


@dataclass(slots=True)
class RawJob:
    """One posting as returned by a source, before any DB concerns."""

    source: str
    external_id: str
    company: str
    title: str
    location: str
    remote: bool
    description: str
    apply_url: str
    posted_at: datetime | None


def strip_html(raw: str) -> str:
    """Greenhouse returns escaped HTML; we want plain text for the LLM later."""
    text = html.unescape(raw or "")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)  # entities can survive one pass (&amp;lt;)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _WS_RE.sub("\n\n", text).strip()
