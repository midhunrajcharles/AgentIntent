import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "agentintent"))

from main import app, _rate_store, intents_db, _seed_demo


@pytest.fixture(autouse=True)
def clear_store():
    intents_db.clear()
    _rate_store.clear()
    yield
    intents_db.clear()
    _rate_store.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared payloads
# ---------------------------------------------------------------------------
DECLARE_PAYLOAD = {
    "agent_id": "test-agent",
    "intent_type": "authorize_payment",
    "details": {
        "target": "https://payment.example.com/pay",
        "amount": 100,
        "currency": "USD",
    },
    "timeout_seconds": 3600,
}

VERIFY_PAYLOAD = {
    "verifier_id": "auditor-001",
    "accepts": True,
    "reason": "Intent matches PO-4421",
}

COMPLETE_PAYLOAD = {
    "reporter_id": "supplier-001",
    "outcome": "fulfilled",
    # actual_details mirrors DECLARE_PAYLOAD details so breach_detected is False
    "actual_details": {
        "target": "https://payment.example.com/pay",
        "amount": 100,
        "currency": "USD",
    },
}


# ---------------------------------------------------------------------------
# Fixtures that walk the state machine
# ---------------------------------------------------------------------------
@pytest.fixture
def declared_intent(client):
    r = client.post("/api/v1/intent/declare", json=DECLARE_PAYLOAD)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def verified_intent(client, declared_intent):
    iid = declared_intent["intent_id"]
    r = client.post(f"/api/v1/intent/{iid}/verify", json=VERIFY_PAYLOAD)
    assert r.status_code == 200, r.text
    return client.get(f"/api/v1/intent/{iid}").json()


@pytest.fixture
def completed_intent(client, verified_intent):
    iid = verified_intent["intent_id"]
    r = client.post(f"/api/v1/intent/{iid}/complete", json=COMPLETE_PAYLOAD)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def demo_intent(client):
    """Re-seed the demo intent (cleared by autouse fixture) and return its record."""
    _seed_demo()
    return intents_db["intent_demo000000"]
