from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base, configure_engine, get_db
from app.core.time import utcnow
from app.main import app
from app.models import User
from app.services.auth_service import bootstrap_admin, register_user
from app.schemas.auth import RegisterRequest


@pytest.fixture()
def db_engine(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = configure_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    # The DB file lives in tmp_path; assignments <-> assignment_versions is a cyclic FK,
    # so drop_all fails on SQLite. Disposing the engine is enough.
    engine.dispose()


@pytest.fixture()
def db(db_engine) -> Session:
    from app.core.database import SessionLocal

    session = SessionLocal()
    bootstrap_admin(session, "admin@demo.local", "DemoPass123!")
    yield session
    session.close()


@pytest.fixture()
def client(db_engine, db):
    def _override():
        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_header(client: TestClient, email: str, password: str = "DemoPass123!") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_instructor(db: Session) -> User:
    from app.models.user import User as UserModel

    admin = db.query(UserModel).filter(UserModel.role == "platform_admin").one()
    return register_user(
        db,
        RegisterRequest(
            email="instructor@demo.local",
            password="DemoPass123!",
            full_name="Instructor",
            role="instructor",
        ),
        actor=admin,
    )


def make_learner(db: Session, email: str = "learner@demo.local", student_number: str = "STU-1") -> User:
    return register_user(
        db,
        RegisterRequest(
            email=email,
            password="DemoPass123!",
            full_name="Learner",
            role="learner",
            student_number=student_number,
        ),
        actor=None,
    )


def future_due():
    return (utcnow() + timedelta(days=7)).isoformat()


@pytest.fixture()
def world(client, db):
    """A course with one instructor, plus builders for learners, assignments, submissions and grades."""
    from tests.helpers import World

    return World(client, db)
