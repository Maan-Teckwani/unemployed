"""A visible Playwright assistant with deliberate safety stops.

It never handles credentials, CAPTCHA, protected demographic questions, or
final submission implicitly. The browser remains visible so the user can see
and interrupt every action.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from uuid import uuid4

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from app.config import REPO_ROOT

SAFE_FIELDS = {
    "name": ("name", "full name", "first name", "last name"),
    "email": ("email", "e-mail"),
    "phone": ("phone", "mobile", "telephone"),
    "location": ("city", "location", "address"),
    "linkedin": ("linkedin",),
    "github": ("github",),
    "portfolio": ("portfolio", "website", "personal site"),
}
BLOCKED_TERMS = (
    "password",
    "captcha",
    "authorization",
    "sponsorship",
    "visa",
    "gender",
    "race",
    "ethnicity",
    "disability",
    "veteran",
    "demographic",
)


class BrowserAssistant:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, dict] = {}
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    def _context_or_start(self) -> BrowserContext:
        if self._context is not None:
            return self._context
        self._playwright = sync_playwright().start()
        profile_dir = REPO_ROOT / "data" / "browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._context = self._playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=False, channel="msedge"
        )
        return self._context

    def start(self, job_id: int, url: str, candidate, resume_path: str) -> dict:
        with self._lock:
            page = self._context_or_start().new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            session_id = str(uuid4())
            session = {
                "session_id": session_id,
                "job_id": job_id,
                "state": "waiting_for_login",
                "message": "Log in if required, complete any CAPTCHA, then choose Prepare application.",
                "safe_fields_filled": 0,
                "blocked_fields": [],
                "application_url": url,
                "page": page,
                "candidate": candidate,
                "resume_path": resume_path,
            }
            self._sessions[session_id] = session
            return self._public(session)

    def prepare(self, session_id: str) -> dict:
        with self._lock:
            session = self._get(session_id)
            page: Page = session["page"]
            values = {
                "name": session["candidate"].name,
                "email": session["candidate"].email,
                "phone": session["candidate"].phone,
                "location": session["candidate"].location,
            }
            filled = 0
            blocked: list[str] = []
            for locator in page.locator("input, textarea").all():
                descriptor = " ".join(
                    filter(
                        None,
                        [
                            locator.get_attribute("name"),
                            locator.get_attribute("id"),
                            locator.get_attribute("aria-label"),
                            locator.get_attribute("placeholder"),
                        ],
                    )
                ).lower()
                if any(term in descriptor for term in BLOCKED_TERMS):
                    blocked.append(descriptor[:120])
                    continue
                field = next(
                    (
                        key
                        for key, terms in SAFE_FIELDS.items()
                        if any(term in descriptor for term in terms)
                    ),
                    None,
                )
                value = values.get(field or "")
                if value and awaitable_fill(locator, value):
                    filled += 1

            resume_path = session["resume_path"]
            if resume_path and Path(resume_path).exists():
                for upload in page.locator('input[type="file"]').all():
                    descriptor = " ".join(
                        filter(
                            None,
                            [
                                upload.get_attribute("name"),
                                upload.get_attribute("id"),
                                upload.get_attribute("aria-label"),
                            ],
                        )
                    ).lower()
                    if "resume" in descriptor or "cv" in descriptor:
                        upload.set_input_files(resume_path)
                        break
            session.update(
                state="ready_for_review",
                message="Review every field. Sensitive questions remain for you. Submit only when ready.",
                safe_fields_filled=filled,
                blocked_fields=blocked,
            )
            return self._public(session)

    def submit(self, session_id: str) -> dict:
        with self._lock:
            session = self._get(session_id)
            page: Page = session["page"]
            # Do not guess which submit button is correct. The user must confirm
            # in the visible browser by using this endpoint from the UI.
            buttons = page.get_by_role("button", name="submit")
            if buttons.count() != 1:
                raise ValueError("Could not identify exactly one Submit button; submit manually.")
            buttons.first.click()
            session.update(
                state="submitted",
                message="Submitted. Verify the confirmation page and update the application status if needed.",
            )
            return self._public(session)

    def _get(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("application assistant session not found")
        return session

    @staticmethod
    def _public(session: dict) -> dict:
        return {
            key: session[key]
            for key in (
                "session_id",
                "job_id",
                "state",
                "message",
                "safe_fields_filled",
                "blocked_fields",
                "application_url",
            )
        }


def awaitable_fill(locator, value: str) -> bool:
    try:
        if locator.is_visible() and locator.is_editable():
            locator.fill(value)
            return True
    except Exception:
        return False
    return False


assistant = BrowserAssistant()
