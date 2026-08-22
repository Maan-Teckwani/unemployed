"""Tests for Roadmap API endpoints and KB integration."""
from unittest.mock import patch

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.roadmap import _clean_bullet
from app.api import roadmap as roadmap_api
from app.db.models import KBChunk, SkillRoadmap
from app.db.session import Base
from app.schemas import RoadmapGenerateIn, RoadmapUpdateIn


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        yield session


@pytest.fixture(autouse=True)
def no_llm():
    """Generation must not reach for Ollama here — the deterministic blueprint is
    what these tests are about, and a live model makes them slow and flaky."""
    with patch("app.ai.roadmap.generate_json", side_effect=RuntimeError("no llm")):
        yield


def _create(db, **kwargs) -> SkillRoadmap:
    payload = RoadmapGenerateIn(
        target_skills=kwargs.get("target_skills", ["Kafka", "Redis", "Docker"]),
        role_family="backend",
        estimated_weeks=3,
    )
    return roadmap_api.create_roadmap(payload, db=db)


def _finish_all(db, roadmap: SkillRoadmap) -> SkillRoadmap:
    milestones = [{**m, "completed": True} for m in roadmap.milestones]
    return roadmap_api.update_roadmap(
        roadmap.id, RoadmapUpdateIn(milestones=milestones), db=db
    )


def test_roadmap_crud_and_complete_to_kb(db):
    created = _create(db)
    assert created.id is not None
    assert created.status == "in_progress"
    assert "Kafka" in created.target_skills
    assert len(created.milestones) >= 2

    roadmap_id = created.id

    all_roadmaps = roadmap_api.list_roadmaps(db=db)
    assert len(all_roadmaps) == 1
    assert all_roadmaps[0].id == roadmap_id

    single = roadmap_api.get_roadmap(roadmap_id, db=db)
    assert single.title == created.title

    updated = _finish_all(db, single)
    assert all(m["completed"] for m in updated.milestones)

    vec = np.zeros(384, dtype=np.float32).tolist()
    with patch("app.api.roadmap.embed_passage", return_value=vec):
        res = roadmap_api.complete_to_kb(roadmap_id, db=db)
        assert res["status"] == "ok"
        assert "chunk_id" in res

    chunk = db.get(KBChunk, res["chunk_id"])
    assert chunk is not None
    assert chunk.type == "project"
    assert "Kafka" in chunk.technologies

    final_roadmap = db.get(SkillRoadmap, roadmap_id)
    assert final_roadmap.status == "completed"

    roadmap_api.delete_roadmap(roadmap_id, db=db)
    assert db.get(SkillRoadmap, roadmap_id) is None


def test_unfinished_roadmap_cannot_enter_the_kb(db):
    """A blueprint is a plan, not an accomplishment: it may not become resume evidence."""
    created = _create(db)

    with pytest.raises(HTTPException) as err:
        roadmap_api.complete_to_kb(created.id, db=db)
    assert err.value.status_code == 400

    assert db.get(SkillRoadmap, created.id).status == "in_progress"
    assert db.query(KBChunk).count() == 0


def test_unknown_status_is_rejected(db):
    created = _create(db)
    with pytest.raises(HTTPException) as err:
        roadmap_api.update_roadmap(
            created.id, RoadmapUpdateIn(status="done-ish"), db=db
        )
    assert err.value.status_code == 422


def test_model_label_is_stripped_from_the_bullet():
    """The model copies the schema's wording back often enough that one click
    put "STAR-format bullet point: ..." into a real Knowledge Base."""
    assert (
        _clean_bullet("STAR-format bullet point: Implemented a Kubernetes platform.")
        == "Implemented a Kubernetes platform."
    )
    assert _clean_bullet("STAR format: Built a thing.") == "Built a thing."

    # A colon inside a real bullet is not a label, and keeps its sentence whole.
    intact = "Implemented a platform with Docker: one container per service."
    assert _clean_bullet(intact) == intact


def test_generated_bullet_carries_no_invented_metrics(db):
    """The project has not been built yet, so its bullet may not claim measurements."""
    created = _create(db)
    assert "%" not in created.resume_bullet_preview
    assert "msgs/sec" not in created.resume_bullet_preview
