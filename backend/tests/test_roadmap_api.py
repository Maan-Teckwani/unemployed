"""Tests for Roadmap API endpoints and KB integration."""
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import roadmap as roadmap_api
from app.db.models import KBChunk, SkillRoadmap
from app.db.session import Base
from app.schemas import RoadmapGenerateIn, RoadmapUpdateIn, SkillSimulateIn


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        yield session


def test_roadmap_crud_and_complete_to_kb(db):
    # 1. Create a roadmap
    payload = RoadmapGenerateIn(
        target_skills=["Kafka", "Redis", "Docker"],
        role_family="backend",
        estimated_weeks=3,
    )
    created = roadmap_api.create_roadmap(payload, db=db)
    assert created.id is not None
    assert created.status == "in_progress"
    assert "Kafka" in created.target_skills
    assert len(created.milestones) >= 2

    roadmap_id = created.id

    # 2. List roadmaps
    all_roadmaps = roadmap_api.list_roadmaps(db=db)
    assert len(all_roadmaps) == 1
    assert all_roadmaps[0].id == roadmap_id

    # 3. Get single roadmap
    single = roadmap_api.get_roadmap(roadmap_id, db=db)
    assert single.title == created.title

    # 4. Update milestone status
    updated_milestones = [dict(m) for m in single.milestones]
    updated_milestones[0]["completed"] = True
    update_payload = RoadmapUpdateIn(milestones=updated_milestones)
    updated = roadmap_api.update_roadmap(roadmap_id, update_payload, db=db)
    assert updated.milestones[0]["completed"] is True

    # 5. Complete to Knowledge Base
    vec = np.zeros(384, dtype=np.float32).tolist()
    with patch("app.api.roadmap.embed_passage", return_value=vec):
        res = roadmap_api.complete_to_kb(roadmap_id, db=db)
        assert res["status"] == "ok"
        assert "chunk_id" in res

    # Verify chunk exists in DB
    chunk = db.get(KBChunk, res["chunk_id"])
    assert chunk is not None
    assert chunk.type == "project"
    assert "Kafka" in chunk.technologies

    # Verify roadmap status marked completed
    final_roadmap = db.get(SkillRoadmap, roadmap_id)
    assert final_roadmap.status == "completed"

    # 6. Delete roadmap
    roadmap_api.delete_roadmap(roadmap_id, db=db)
    assert db.get(SkillRoadmap, roadmap_id) is None
