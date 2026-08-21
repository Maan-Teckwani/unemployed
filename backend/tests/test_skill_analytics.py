"""Tests for Macro Skill Gap Intelligence and Skill Simulation math."""
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.skill_analytics import analyze_market_skills, categorize_skill, simulate_skill_acquisition
from app.db.models import Job, JobEmbedding, JobRequirements, KBChunk, Match
from app.db.session import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        # Candidate has Python and PostgreSQL
        vec = np.zeros(384, dtype=np.float32)
        vec[0] = 1.0
        session.add(
            KBChunk(
                id=1,
                type="project",
                title="Backend API",
                accomplishment="Built backend using Python and PostgreSQL",
                technologies=["Python", "PostgreSQL"],
                skills=["Python", "PostgreSQL", "REST"],
                embedding=vec.tolist(),
            )
        )

        # Job 1: Demands Python (mastered), Docker (missing), Redis (missing)
        session.add(
            Job(
                id=1,
                source="greenhouse",
                external_id="j1",
                company="Stripe",
                title="Backend Engineer",
                status="active",
            )
        )
        session.add(
            JobRequirements(
                job_id=1,
                required_skills=["Python", "Docker"],
                preferred_skills=["Redis"],
                confidence=0.9,
            )
        )
        session.add(
            JobEmbedding(
                job_id=1,
                embedding=vec.tolist(),
            )
        )

        # Job 2: Demands Docker (missing), Kafka (missing)
        session.add(
            Job(
                id=2,
                source="lever",
                external_id="j2",
                company="PhonePe",
                title="Software Engineer - Systems",
                status="active",
            )
        )
        session.add(
            JobRequirements(
                job_id=2,
                required_skills=["Docker", "Kafka"],
                preferred_skills=["Python"],
                confidence=0.9,
            )
        )
        session.add(
            JobEmbedding(
                job_id=2,
                embedding=vec.tolist(),
            )
        )

        session.commit()
        yield session


def test_categorize_skill():
    assert categorize_skill("Python") == "Languages"
    assert categorize_skill("FastAPI") == "Backend & APIs"
    assert categorize_skill("PostgreSQL") == "Databases & Storage"
    assert categorize_skill("Docker") == "Cloud & DevOps"
    assert categorize_skill("React") == "Frontend & Mobile"
    assert categorize_skill("Kafka") == "Data, AI & Messaging"
    assert categorize_skill("Pytest") == "Testing & Core CS"


def test_analyze_market_skills(db):
    report = analyze_market_skills(db)

    assert report["total_jobs_analyzed"] == 2
    assert report["candidate_skills_count"] >= 2
    assert report["market_readiness_pct"] > 0

    missing_names = [s["skill"].lower() for s in report["top_missing_skills"]]
    assert "docker" in missing_names
    assert "kafka" in missing_names

    mastered_names = [s["skill"].lower() for s in report["top_mastered_skills"]]
    assert "python" in mastered_names


def test_simulate_skill_acquisition(db):
    sim = simulate_skill_acquisition(["Docker", "Kafka"], db=db)

    assert sim["avg_lift"] > 0
    assert sim["new_avg_score"] > sim["previous_avg_score"]
    assert len(sim["impacted_jobs"]) > 0
