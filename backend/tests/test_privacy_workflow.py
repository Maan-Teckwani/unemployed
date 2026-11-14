import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import privacy, workflow
from app.db.models import CandidateProfile, Company, Job
from app.db.session import Base
from app.schemas import DeleteDataIn, WorkflowSettingsIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def test_workflow_settings_are_persistent_and_validate_timezone():
    db = _db()
    assert workflow.get_workflow_settings(db).follow_up_days == 7
    updated = workflow.update_workflow_settings(
        WorkflowSettingsIn(follow_up_days=14, timezone="Asia/Kolkata"), db
    )
    assert updated.follow_up_days == 14
    assert workflow.get_workflow_settings(db).timezone == "Asia/Kolkata"


def test_backup_is_local_and_excludes_connector_credentials():
    db = _db()
    db.add_all([
        CandidateProfile(name="Candidate"),
        Company(source="greenhouse", token="do-not-export", name="Acme"),
    ])
    db.commit()
    response = privacy.export_data(db)
    payload = json.loads(response.body)
    assert payload["data"]["candidate_profile"][0]["name"] == "Candidate"
    assert "do-not-export" not in response.body.decode()


def test_delete_requires_explicit_confirmation_and_removes_rows():
    db = _db()
    db.add(Job(source="manual", external_id="1", company="Acme", title="Engineer"))
    db.commit()
    try:
        privacy.delete_data(DeleteDataIn(confirmation="delete"), db)
    except Exception as error:
        assert getattr(error, "status_code", None) == 400
    else:
        raise AssertionError("lowercase confirmation must not delete")
    privacy.delete_data(DeleteDataIn(confirmation="DELETE"), db)
    assert db.query(Job).count() == 0
