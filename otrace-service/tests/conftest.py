"""Test fixtures for the OTrace service.

Every test runs against a throwaway SQLite database in a temporary
directory. ``OTRACE_DB_PATH`` is set before the app is imported, so the
real ``otrace.db`` is never touched.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))


@pytest.fixture(scope="session", autouse=True)
def _throwaway_database(tmp_path_factory):
    """Point the service at a temporary database for the whole session."""
    db_path = tmp_path_factory.mktemp("otrace") / "test.db"
    os.environ["OTRACE_DB_PATH"] = str(db_path)
    yield
    os.environ.pop("OTRACE_DB_PATH", None)


@pytest.fixture(scope="session")
def client(_throwaway_database):
    """FastAPI test client bound to the temporary database."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


@pytest.fixture
def unique() -> str:
    """A short unique suffix, so tests never collide on names."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def accepted_consent(client, unique) -> dict:
    """An offered-and-accepted consent, with its operator and user."""
    operator = f"operator-{unique}"
    user = f"patient-{unique}"
    response = client.post(
        "/consents/offer/",
        params={"expiry_timestamp": "2030-01-01T00:00:00"},
        json={
            "operator": {"name": operator},
            "user": {"name": user},
            "data": {"description": "ICU vitals"},
            "operations": [{"operation_type": "read"}],
        },
    )
    consent = response.json()
    client.post(f"/consents/accept/{consent['id']}/", json={"name": user})
    return {"id": consent["id"], "operator": operator, "user": user}
