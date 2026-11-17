"""Fixtures de teste: cada teste usa uma pasta de dados temporária e isolada.

Nenhum teste lê ou grava em ``backend/bim_schedule.db``, ``backend/uploads`` ou na
pasta de dados real do usuário.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import SessionLocal
from app.main import create_app


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        DATA_DIR=tmp_path / "data",
        LEGACY_DIR=tmp_path / "legacy",
        ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"],
        ENVIRONMENT="test",
        JOB_CANCEL_GRACE_SECONDS=3.0,
        JOB_POLL_INTERVAL_SECONDS=0.05,
        LOG_LEVEL="WARNING",
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def runtime(client):
    return client.app.state.runtime


@pytest.fixture
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
