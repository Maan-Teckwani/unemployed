"""Which companies we track, and which connector reads each one.

Companies live in the database so they can be searched for and added from the
settings page without a restart. `discovered.json` — written by
`app.ingestion.discover` — seeds that table the first time it is empty, so a
fresh clone still starts with a working set of boards.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors import ashby, greenhouse, lever, recruitee, smartrecruiters, workday
from app.db.models import Company as CompanyRow

DISCOVERED_PATH = Path(__file__).resolve().parent / "discovered.json"

# source -> fetch(token, company, region) -> list[RawJob]
CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
    "recruitee": recruitee.fetch,
}


@dataclass(frozen=True, slots=True)
class Company:
    source: str
    token: str
    name: str


def load_companies(db: Session) -> list[Company]:
    """Enabled companies, seeding from discovered.json if the table is empty."""
    rows = list(db.scalars(select(CompanyRow).where(CompanyRow.enabled.is_(True))))
    if not rows:
        seed_from_file(db)
        rows = list(db.scalars(select(CompanyRow).where(CompanyRow.enabled.is_(True))))
    return [Company(r.source, r.token, r.name) for r in rows if r.source in CONNECTORS]


def seed_from_file(db: Session) -> int:
    """Import discovered.json into the companies table. Returns rows added."""
    if not DISCOVERED_PATH.exists():
        return 0
    entries = json.loads(DISCOVERED_PATH.read_text(encoding="utf-8"))

    existing = {(r.source, r.token) for r in db.scalars(select(CompanyRow))}
    added = 0
    for entry in entries:
        key = (entry.get("source"), entry.get("token"))
        if key in existing or entry.get("source") not in CONNECTORS:
            continue
        db.add(
            CompanyRow(
                source=entry["source"],
                token=entry["token"],
                name=entry.get("name") or entry["token"],
                matched_jobs=entry.get("india_jobs") or entry.get("matched_jobs") or 0,
            )
        )
        existing.add(key)
        added += 1
    db.commit()
    return added
