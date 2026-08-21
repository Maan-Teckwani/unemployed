"""FastAPI application entrypoint.

Sprint 1: a minimal app with a health check that confirms the API is up and can
reach Postgres. Routers (kb, jobs, matches, ...) get mounted here as we build them.
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import (
    applications,
    companies,
    jobs,
    kb,
    matches,
    outreach,
    pipeline,
    preferences,
    profile,
    projects,
    resumes,
    roadmap,
    setup,
    templates,
)
from app.db.retention import start_sweeper
from app.db.session import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.release_stale_runs()
    # Generated resumes expire (see app.db.retention). The sweeper is what makes
    # that true while the app sits idle, rather than only when a request lands.
    start_sweeper()
    yield


app = FastAPI(title="AI Career Assistant", version="0.1.0", lifespan=lifespan)

# The Next.js dev server calls this API on :8000, and a browser treats
# "localhost" and "127.0.0.1" as different origins even though they reach the
# same machine. Pinning an exact port was a trap: when :3000 is already taken
# Next silently starts on :3001, every preflight then fails CORS, and the
# CORSMiddleware answers 400 before the request reaches a route - so the app
# renders completely empty with a healthy backend and no error on the page.
# Any localhost port is allowed instead. This binds to 127.0.0.1 and holds
# nothing but your own data, so the origin check was never the security
# boundary - not being reachable off this machine is.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kb.router)
app.include_router(jobs.router)
app.include_router(matches.router)
app.include_router(resumes.router)
app.include_router(applications.router)
app.include_router(preferences.router)
app.include_router(outreach.router)
app.include_router(projects.router)
app.include_router(companies.router)
app.include_router(pipeline.router)
app.include_router(setup.router)
app.include_router(templates.router)
app.include_router(profile.router)
app.include_router(roadmap.router)



@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness + DB connectivity check."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}
