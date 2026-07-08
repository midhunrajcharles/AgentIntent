import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add agentintent service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "agentintent"))

from main import app
from utils import _intents


@pytest.fixture(autouse=True)
def clear_store():
    _intents.clear()
    yield
    _intents.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registered_intent(client):
    r = client.post("/api/v1/intents/register", json={
        "agent_id": "test-agent",
        "action": "test_action",
        "target": "https://example.com/api",
        "parameters": {"key": "value"},
        "ttl_seconds": 3600,
    })
    assert r.status_code == 201
    return r.json()
