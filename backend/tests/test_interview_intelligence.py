from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import interview
from app.db.models import CompanyIntel, Job, KBChunk
from app.db.session import Base
from app.schemas import CompanyIntelIn, InterviewPrepIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def test_company_intelligence_stores_user_supplied_facts():
    db = _db()
    row = interview.add_company_intelligence(
        CompanyIntelIn(company_name="Acme", title="Careers page",
                       content="Acme builds search tools.", source_url="https://acme.test"),
        db,
    )
    assert row["company_name"] == "Acme"
    assert db.query(CompanyIntel).count() == 1


def test_interview_prep_filters_model_citations_to_stored_evidence(monkeypatch):
    db = _db()
    db.add(Job(id=1, source="manual", external_id="1", company="Acme",
               title="Backend Engineer", description="Python APIs"))
    db.add(KBChunk(id=7, type="experience", title="API project",
                   accomplishment="Built Python APIs", embedding=[0.0]))
    db.commit()
    monkeypatch.setattr(interview.generator, "generate", lambda *args: {
        "questions": [{"question": "Tell me about APIs", "answer": "I built APIs.",
                       "source_chunk_ids": [7]}],
        "talking_points": ["Python APIs"],
        "source_chunk_ids": [7],
    })
    # Avoid embedding/model work in this route while retaining the route contract.
    monkeypatch.setattr(interview, "retrieve", lambda *args, **kwargs: [db.get(KBChunk, 7)])
    result = interview.create_interview_prep(1, InterviewPrepIn(), db)
    assert result["source_chunk_ids"] == [7]
    assert result["questions"][0]["source_chunk_ids"] == [7]
