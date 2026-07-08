# SKILL: Testing Patterns for AgentIntent

## PURPOSE
Write tests that validate all AgentIntent endpoints, achieve >90% coverage, and simulate the exact judge evaluation procedure.

---

## TEST SETUP (conftest.py)

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from main import app
from store import intents  # direct access to clear between tests

@pytest.fixture(autouse=True)
def clear_store():
    """Clear in-memory store before each test — no state leakage."""
    intents.clear()
    yield
    intents.clear()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def registered_intent(client):
    """Pre-register an intent for tests that need existing data."""
    response = client.post("/api/v1/intents/register", json={
        "agent_id": "test-agent",
        "action": "test_action",
        "target": "https://example.com",
        "parameters": {"key": "value"},
        "ttl_seconds": 3600,
    })
    assert response.status_code == 201
    return response.json()
```

---

## CORE ENDPOINT TESTS

```python
# tests/test_intents.py
import pytest
from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "agent_id": "agent-001",
    "action": "transfer_funds",
    "target": "https://payment.example.com/transfer",
    "parameters": {"amount": 100, "currency": "USD"},
    "ttl_seconds": 3600,
}

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    def test_health_response_shape(self, client):
        r = client.get("/api/v1/health")
        data = r.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert "intents_stored" in data


class TestRegisterIntent:
    def test_register_returns_201(self, client):
        r = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        assert r.status_code == 201

    def test_register_returns_intent_id(self, client):
        r = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        data = r.json()
        assert "intent_id" in data
        assert len(data["intent_id"]) > 0

    def test_register_returns_proof_hash(self, client):
        r = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        data = r.json()
        assert "proof_hash" in data
        assert len(data["proof_hash"]) == 64  # SHA256 hex = 64 chars

    def test_register_status_is_active(self, client):
        r = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        assert r.json()["status"] == "active"

    def test_register_missing_agent_id_returns_422(self, client):
        payload = VALID_PAYLOAD.copy()
        del payload["agent_id"]
        r = client.post("/api/v1/intents/register", json=payload)
        assert r.status_code == 422

    def test_register_missing_action_returns_422(self, client):
        payload = VALID_PAYLOAD.copy()
        del payload["action"]
        r = client.post("/api/v1/intents/register", json=payload)
        assert r.status_code == 422

    def test_register_missing_target_returns_422(self, client):
        payload = VALID_PAYLOAD.copy()
        del payload["target"]
        r = client.post("/api/v1/intents/register", json=payload)
        assert r.status_code == 422

    def test_register_empty_body_returns_422(self, client):
        r = client.post("/api/v1/intents/register", json={})
        assert r.status_code == 422

    def test_register_default_ttl(self, client):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "ttl_seconds"}
        r = client.post("/api/v1/intents/register", json=payload)
        assert r.status_code == 201

    def test_register_two_intents_get_different_ids(self, client):
        r1 = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        r2 = client.post("/api/v1/intents/register", json=VALID_PAYLOAD)
        assert r1.json()["intent_id"] != r2.json()["intent_id"]


class TestGetIntent:
    def test_get_existing_intent(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}")
        assert r.status_code == 200

    def test_get_returns_correct_data(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}")
        data = r.json()
        assert data["intent_id"] == intent_id
        assert data["agent_id"] == "test-agent"
        assert data["action"] == "test_action"

    def test_get_nonexistent_returns_404(self, client):
        r = client.get("/api/v1/intents/doesnotexist")
        assert r.status_code == 404

    def test_get_404_has_error_field(self, client):
        r = client.get("/api/v1/intents/doesnotexist")
        data = r.json()
        assert "error" in data or "detail" in data


class TestVerifyIntent:
    def test_verify_returns_200(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}/verify")
        assert r.status_code == 200

    def test_verify_valid_intent(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}/verify")
        data = r.json()
        assert data["valid"] is True
        assert data["match"] is True

    def test_verify_hashes_match(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}/verify")
        data = r.json()
        assert data["proof_hash"] == data["computed_hash"]

    def test_verify_nonexistent_returns_404(self, client):
        r = client.get("/api/v1/intents/doesnotexist/verify")
        assert r.status_code == 404

    def test_verify_response_has_required_fields(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.get(f"/api/v1/intents/{intent_id}/verify")
        data = r.json()
        for field in ["intent_id", "valid", "status", "proof_hash", "computed_hash", "match", "message"]:
            assert field in data, f"Missing field: {field}"


class TestRevokeIntent:
    def test_revoke_returns_200(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        r = client.delete(f"/api/v1/intents/{intent_id}")
        assert r.status_code == 200

    def test_revoke_changes_status(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        client.delete(f"/api/v1/intents/{intent_id}")
        r = client.get(f"/api/v1/intents/{intent_id}")
        assert r.json()["status"] == "revoked"

    def test_revoke_nonexistent_returns_404(self, client):
        r = client.delete("/api/v1/intents/doesnotexist")
        assert r.status_code == 404

    def test_revoked_intent_verify_shows_invalid(self, client, registered_intent):
        intent_id = registered_intent["intent_id"]
        client.delete(f"/api/v1/intents/{intent_id}")
        r = client.get(f"/api/v1/intents/{intent_id}/verify")
        assert r.json()["valid"] is False
```

---

## JUDGE SIMULATION TEST

```python
# tests/test_judge_simulation.py
"""
Simulates exactly what the NandaHack judge will do.
This test MUST pass 100% for full score.
"""

class TestJudgeSimulation:
    def test_full_judge_workflow(self, client):
        """
        Judge task 1: Register an intent
        Judge task 2: Retrieve and confirm it exists
        Judge task 3: Verify cryptographic proof
        """
        # Task 1: Register
        register_r = client.post("/api/v1/intents/register", json={
            "agent_id": "judge-agent",
            "action": "evaluate_submission",
            "target": "https://hackathon.nanda.ai/evaluate",
            "parameters": {"team": "NandaHackBot", "submission_id": "001"},
        })
        assert register_r.status_code == 201, f"Registration failed: {register_r.text}"
        intent = register_r.json()
        intent_id = intent["intent_id"]
        assert intent_id, "No intent_id returned"
        assert intent["status"] == "active"

        # Task 2: Retrieve
        get_r = client.get(f"/api/v1/intents/{intent_id}")
        assert get_r.status_code == 200, f"Retrieval failed: {get_r.text}"
        retrieved = get_r.json()
        assert retrieved["intent_id"] == intent_id
        assert retrieved["agent_id"] == "judge-agent"

        # Task 3: Verify
        verify_r = client.get(f"/api/v1/intents/{intent_id}/verify")
        assert verify_r.status_code == 200, f"Verification failed: {verify_r.text}"
        verification = verify_r.json()
        assert verification["valid"] is True, f"Intent not valid: {verification}"
        assert verification["match"] is True, f"Hash mismatch: {verification}"

    def test_judge_error_recovery_invalid_id(self, client):
        """Judge tests: what happens with bad intent_id?"""
        r = client.get("/api/v1/intents/INVALID_ID_99999")
        assert r.status_code == 404
        data = r.json()
        assert "error" in data or "detail" in data

    def test_judge_cold_start_health_check(self, client):
        """Judge always checks health first."""
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"
```

---

## RUNNING TESTS

```bash
# Run all tests with coverage
pytest tests/ -v --tb=short --cov=. --cov-report=term-missing

# Run only judge simulation
pytest tests/test_judge_simulation.py -v

# Run with fail-fast (stop at first failure)
pytest tests/ -x -v

# Expected output target
# PASSED: ≥90% of tests
# Coverage: ≥90%
```

---

## COVERAGE REQUIREMENTS

| Module | Target |
|--------|--------|
| main.py | 95% |
| models.py | 100% |
| store.py | 95% |
| hashing.py | 100% |
| routers/intents.py | 95% |
| middleware.py | 80% |
| **Overall** | **≥90%** |

---

## PRE-SUBMISSION CHECKLIST

```bash
# 1. All tests pass
pytest tests/ -v
# Expected: no FAILED, ≥90% PASSED

# 2. Coverage check
pytest --cov=. --cov-report=term-missing | grep TOTAL
# Expected: TOTAL ... 90%+

# 3. Live endpoint smoke test
curl https://your-service.onrender.com/api/v1/health
# Expected: {"status": "healthy", ...}

# 4. Judge simulation via curl (not pytest)
INTENT=$(curl -s -X POST https://your-service.onrender.com/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"judge","action":"test","target":"https://example.com","parameters":{}}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")
echo "Intent ID: $INTENT"
curl https://your-service.onrender.com/api/v1/intents/$INTENT/verify
# Expected: {"valid": true, "match": true, ...}
```
