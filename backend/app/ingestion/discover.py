"""Find which companies actually have a public job board, on which platform.

    python -m app.ingestion.discover [--limit N] [--refresh]

Manually collecting board tokens does not scale — most guesses 404, and the ones
that work are unevenly spread across four different ATS vendors. This turns that
into a measured sweep: generate candidate slugs from company names, probe every
platform, and keep what resolves.

Two things make the result trustworthy rather than merely large:

* **Collision check.** Slugs are not unique across vendors — Ashby's "navi" is a
  US startup, not the Indian neobank. A board only enters the registry if it
  actually returns India-relevant jobs.
* **Caching.** Results are written to `discovered.json`, so a re-run does not
  re-probe hundreds of URLs that already answered.

Politeness: 8 concurrent requests with short timeouts.
"""
import argparse
import re
from concurrent.futures import ThreadPoolExecutor

import httpx
from sqlalchemy import func, select

from app.connectors import workday
from app.connectors.companies import SEED_COMPANIES
from app.db.models import Company as CompanyRow
from app.db.models import Preferences
from app.db.session import SessionLocal
from app.ingestion.relevance import DEFAULT_REGION, is_relevant

MAX_WORKERS = 8
PROBE_TIMEOUT = 10.0
# Below this, a 200 response is an empty stub rather than a real board.
MIN_BODY_BYTES = 400

# Workday is deliberately absent. Its API lives at
# `{sub}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}`, and the data centre
# and site name cannot be derived from a company name, so probing for one means
# a cross product of guesses against someone else's servers for every company
# that does not have one. Workday boards are added by token instead; see
# app/connectors/workday.py for the format.
PROBES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
}


def slug_variants(name: str) -> list[str]:
    """Candidate board tokens for a company name, most likely first."""
    lowered = name.lower().strip()
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    hyphen = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    first = compact
    for suffix in ("technologies", "india", "labs", "inc"):
        if compact.endswith(suffix) and len(compact) > len(suffix) + 3:
            first = compact[: -len(suffix)]
            break
    return list(dict.fromkeys(v for v in (compact, hyphen, first) if len(v) >= 3))


def probe(platform: str, slug: str) -> list[dict] | None:
    """Return the board's raw job entries if this slug resolves, else None."""
    try:
        resp = httpx.get(
            PROBES[platform].format(slug=slug), timeout=PROBE_TIMEOUT, follow_redirects=True
        )
    except Exception:  # noqa: BLE001 - unreachable is simply "not found"
        return None
    if resp.status_code != 200 or len(resp.content) < MIN_BODY_BYTES:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    if platform == "greenhouse":
        return data.get("jobs")
    if platform == "lever":
        return data if isinstance(data, list) else None
    if platform == "ashby":
        return data.get("jobs")
    if platform == "recruitee":
        return data.get("offers")
    return data.get("content")


def matched_job_count(platform: str, entries: list[dict], region: str) -> int:
    """How many postings on this board someone in `region` could apply to.

    This is the collision guard: board slugs are not unique across vendors
    (Ashby's "navi" is a US startup, not the Indian neobank), so a board that
    resolves but has no roles for your region is a different company.
    """
    count = 0
    for e in entries or []:
        if platform == "greenhouse":
            location, remote, title = (e.get("location") or {}).get("name", ""), False, e.get("title", "")
        elif platform == "lever":
            location = (e.get("categories") or {}).get("location", "")
            remote, title = (e.get("workplaceType") or "").lower() == "remote", e.get("text", "")
        elif platform == "ashby":
            location, remote, title = e.get("location") or "", bool(e.get("isRemote")), e.get("title", "")
        elif platform == "recruitee":
            location = e.get("location") or ", ".join(
                p for p in (e.get("city"), e.get("country_code")) if p
            )
            remote, title = bool(e.get("remote")), e.get("title", "")
        else:
            loc = e.get("location") or {}
            location, remote, title = loc.get("fullLocation") or "", bool(loc.get("remote")), e.get("name", "")
        if is_relevant(location, remote, title, region):
            count += 1
    return count


# .in as well as .com, because half this list is Indian and half of those are
# not on .com: groww.in, juspay.in, kreditbee.in, payu.in. Guessing only .com
# found one company in a hundred and twenty, and the page scan was not the part
# that was failing.
_TLDS = (".com", ".in")


def domain_variants(name: str) -> list[str]:
    """Candidate company domains, for the careers page step below.

    A guess, and a cheap one to be wrong about: a domain that does not exist
    fails to resolve immediately. Plenty are unguessable ("John Deere" is
    deere.com, Zepto is zepto.co.in, PhysicsWallah is pw.live), which is what
    pasting a link is for.
    """
    compact = re.sub(r"[^a-z0-9]", "", name.lower().strip())
    hyphen = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    stems = [v for v in dict.fromkeys((compact, hyphen)) if len(v) >= 3]
    return [f"{stem}{tld}" for stem in stems for tld in _TLDS]


# Where a board's slug appears when a careers page links to it. Reading the
# slug beats guessing it: Razorpay's Greenhouse board is
# "razorpaysoftwareprivatelimited", which no variant of "Razorpay" produces.
_BOARD_LINKS = {
    "greenhouse": re.compile(
        r"(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)",
        re.I,
    ),
    "lever": re.compile(r"jobs\.lever\.co/([A-Za-z0-9_-]+)", re.I),
    "ashby": re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)", re.I),
    "smartrecruiters": re.compile(
        r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I
    ),
    "recruitee": re.compile(r"https?://([A-Za-z0-9_-]+)\.recruitee\.com", re.I),
}
_WORKDAY_LINK = re.compile(r"https?://[\w-]+\.wd\d+\.myworkdayjobs\.com/[^\s\"'<>)]*", re.I)

_CAREERS_URLS = ("https://careers.{d}", "https://{d}/careers", "https://jobs.{d}")
_PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; unemployed/1.0; "
        "+https://github.com/Maan-Teckwani/unemployed)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}
# Careers pages are large and the links are near the top of what matters. This
# is a cap on how much of one we are willing to read, not on what we accept.
_MAX_PAGE = 400_000


def find_via_careers_page(name: str, region: str = DEFAULT_REGION) -> dict | None:
    """Read a company's careers page and take the board slug out of it.

    The guessing above turns a name into candidate slugs, which works when a
    company's board is named after the company and fails silently when it is
    not. Razorpay is on Greenhouse as "razorpaysoftwareprivatelimited" and was
    counted as having no board at all.

    So this asks the company instead. Their careers page links to whichever
    board they use, and that link carries the exact slug. It also finds
    platforms the slug probes cannot reach at all, which is why Workday is
    handled here rather than separately.

    Not a replacement for the probes: most careers pages build their links in
    JavaScript, so roughly a quarter of companies answer this way. It runs last,
    for names nothing else claimed, and costs three requests against the
    company's own site.
    """
    for domain in domain_variants(name):
        for template in _CAREERS_URLS:
            page = _read(template.format(d=domain))
            if page is None:
                continue
            found = _board_in(page, region)
            if found:
                return {**found, "name": name}
    return None


def _read(url: str) -> str | None:
    try:
        resp = httpx.get(
            url, timeout=PROBE_TIMEOUT, follow_redirects=True, headers=_PAGE_HEADERS
        )
    except Exception:  # noqa: BLE001 - no such site is simply "not found"
        return None
    if resp.status_code != 200:
        return None
    # The final URL matters as much as the body: plenty of careers domains are
    # a redirect straight onto the board.
    return f"{resp.url} {(resp.text or '')[:_MAX_PAGE]}"


def _board_in(page: str, region: str) -> dict | None:
    """The first board named on this page that has jobs for this region."""
    workday_link = _WORKDAY_LINK.search(page)
    if workday_link:
        resolved = workday.resolve(workday_link.group(0), region)
        if resolved:
            return resolved

    for platform, pattern in _BOARD_LINKS.items():
        for slug in dict.fromkeys(pattern.findall(page)):
            entries = probe(platform, slug)
            if entries is None:
                continue
            matched = matched_job_count(platform, entries, region)
            if matched > 0:
                return {
                    "source": platform,
                    "token": slug,
                    "total_jobs": len(entries),
                    "matched_jobs": matched,
                }
    return None


def find_company(name: str, region: str = DEFAULT_REGION) -> dict | None:
    """Locate one company's board. First platform with matching jobs wins.

    Also used by the settings page, so a user can add any company by name.
    """
    for slug in slug_variants(name):
        for platform in PROBES:
            entries = probe(platform, slug)
            if entries is None:
                continue
            matched = matched_job_count(platform, entries, region)
            if matched > 0:
                return {
                    "source": platform,
                    "token": slug,
                    "name": name,
                    "total_jobs": len(entries),
                    "matched_jobs": matched,
                }

    # Nothing claimed this name, so ask the company where its board is rather
    # than guessing at it again. This is also the only route to Workday, which
    # has no slug to probe.
    return find_via_careers_page(name, region)


def discover(names: list[str], region: str = DEFAULT_REGION, on_progress=None) -> list[dict]:
    """Probe every name, reporting as answers come back.

    `on_progress(done, total, message)` is optional so the CLI keeps working
    untouched. The UI needs it: a name that reaches the careers page step costs
    several requests to someone else's site, so a sweep is minutes long and a
    bar that sits at zero until the end looks like a hang.
    """
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = pool.map(lambda n: find_company(n, region), names)
        for i, result in enumerate(results, start=1):
            if result:
                found.append(result)
                print(
                    f"  [{i}/{len(names)}] {result['name']} -> {result['source']}"
                    f"/{result['token']} ({result['matched_jobs']} matching jobs)"
                )
            elif i % 25 == 0:
                print(f"  [{i}/{len(names)}] …")
            if on_progress:
                on_progress(i, len(names), f"Checked {i} of {len(names)}, found {len(found)}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover company job boards.")
    parser.add_argument("--limit", type=int, default=None, help="probe only the first N companies")
    parser.add_argument(
        "--refresh", action="store_true", help="re-probe companies already in the registry"
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        preferences = db.scalar(select(Preferences))
        region = getattr(preferences, "region", None) or DEFAULT_REGION
        known = {(c.source, c.token) for c in db.scalars(select(CompanyRow))}
        known_names = {c.name for c in db.scalars(select(CompanyRow))}

        names = SEED_COMPANIES if args.refresh else [
            n for n in SEED_COMPANIES if n not in known_names
        ]
        names = names[: args.limit] if args.limit else names

        print(f"probing {len(names)} companies for region '{region}' ({len(known)} known)…")
        found = discover(names, region)

        added = 0
        for entry in found:
            if (entry["source"], entry["token"]) in known:
                continue
            db.add(
                CompanyRow(
                    source=entry["source"],
                    token=entry["token"],
                    name=entry["name"],
                    matched_jobs=entry["matched_jobs"],
                )
            )
            known.add((entry["source"], entry["token"]))
            added += 1
        db.commit()
        total = db.scalar(select(func.count()).select_from(CompanyRow)) or 0

    print(f"\n+{added} new · {total} boards tracked")


if __name__ == "__main__":
    main()
