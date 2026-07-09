"""Comprehensive endpoint test suite for AgentIntent service.

28 tests across 6 classes — covers all 4 endpoints, state machine transitions,
breach detection, and rate limiting.

Run:
    cd services/agentintent
    pytest ../tests/test_agentintent_api.py -v --tb=short
"""
import pytest
from conftest import DECLARE_PAYLOAD, VERIFY_PAYLOAD, COMPLETE_PAYLOAD


# ---------------------------------------------------------------------------
# Helper — build a stale/expired record for injection into intents_db
# ---------------------------------------------------------------------------

def _stale_record(intent_id: str) -> dict:
    """Pending intent record whose TTL has long since elapsed (2020)."""
    from utils import _compute_intent_hash
    return {
        "intent_id": intent_id,
        "agent_id": "test-agent",
        "intent_type": "test_action",
        "details": {"target": "https://example.com"},
        "max_cost": None,
        "timeout_seconds": 60,
        "status": "pending",
        "created_at": "2020-01-01T00:00:00+00:00",
        "expires_at": "2020-01-01T00:01:00+00:00",
        "intent_hash": _compute_intent_hash(
            "test-agent", "test_action", {"target": "https://example.com"}
        ),
        "binding_hash": None,
        "verification": None,
        "outcome": None,
        "audit_trail": [],
    }


# ---------------------------------------------------------------------------
# TestHealthEndpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health"""

    def test_health_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_contains_version(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["service"] == "AgentIntent"
        assert "timestamp" in data
        assert "intents_stored" in data


# ---------------------------------------------------------------------------
# TestDeclareIntent
# ---------------------------------------------------------------------------

class TestDeclareIntent:
    """POST /api/v1/intent/declare"""

    def test_declare_valid_intent_returns_201(self, client):
        r = client.post("/api/v1/intent/declare", json=DECLARE_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "pending"
        assert data["intent_id"].startswith("intent_")
        assert data["agent_id"] == DECLARE_PAYLOAD["agent_id"]

    def test_declare_generates_unique_ids(self, client):
        id1 = client.post("/api/v1/intent/declare", json=DECLARE_PAYLOAD).json()["intent_id"]
        id2 = client.post("/api/v1/intent/declare", json=DECLARE_PAYLOAD).json()["intent_id"]
        assert id1 != id2

    def test_declare_includes_hash(self, client):
        data = client.post("/api/v1/intent/declare", json=DECLARE_PAYLOAD).json()
        assert "intent_hash" in data
        assert len(data["intent_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in data["intent_hash"])

    def test_declare_sets_expiry(self, client):
        payload = {**DECLARE_PAYLOAD, "timeout_seconds": 1800}
        data = client.post("/api/v1/intent/declare", json=payload).json()
        assert data["timeout_seconds"] == 1800
        assert data["expires_at"] > data["created_at"]

    def test_declare_missing_agent_id_returns_422(self, client):
        payload = {k: v for k, v in DECLARE_PAYLOAD.items() if k != "agent_id"}
        assert client.post("/api/v1/intent/declare", json=payload).status_code == 422

    def test_declare_missing_intent_type_returns_422(self, client):
        payload = {k: v for k, v in DECLARE_PAYLOAD.items() if k != "intent_type"}
        assert client.post("/api/v1/intent/declare", json=payload).status_code == 422

    def test_declare_empty_details_returns_422(self, client):
        payload = {**DECLARE_PAYLOAD, "details": {}}
        assert client.post("/api/v1/intent/declare", json=payload).status_code == 422

    def test_declare_invalid_target_uri_returns_422(self, client):
        payload = {**DECLARE_PAYLOAD, "details": {"target": "ftp://bad-scheme"}}
        assert client.post("/api/v1/intent/declare", json=payload).status_code == 422

    def test_declare_invalid_intent_type_pattern_returns_422(self, client):
        payload = {**DECLARE_PAYLOAD, "intent_type": "CamelCase"}
        assert client.post("/api/v1/intent/declare", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# TestVerifyIntent
# ---------------------------------------------------------------------------

class TestVerifyIntent:
    """POST /api/v1/intent/{intent_id}/verify"""

    def test_verify_accepted_updates_status(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/verify", json=VERIFY_PAYLOAD)
        assert r.status_code == 200
        assert r.json()["status"] == "verified"
        assert r.json()["accepted"] is True

    def test_verify_rejected_updates_status(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        reject = {**VERIFY_PAYLOAD, "accepts": False, "reason": "Budget exceeded"}
        r = client.post(f"/api/v1/intent/{iid}/verify", json=reject)
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"
        assert r.json()["accepted"] is False

    def test_verify_accepted_includes_binding_hash(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        data = client.post(f"/api/v1/intent/{iid}/verify", json=VERIFY_PAYLOAD).json()
        assert "binding_hash" in data
        assert data["binding_hash"] is not None
        assert len(data["binding_hash"]) == 64

    def test_verify_nonexistent_returns_404(self, client):
        r = client.post("/api/v1/intent/intent_NONEXISTENT99/verify", json=VERIFY_PAYLOAD)
        assert r.status_code == 404

    def test_verify_already_verified_returns_409(self, client, verified_intent):
        iid = verified_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/verify", json=VERIFY_PAYLOAD)
        assert r.status_code == 409

    def test_verify_expired_returns_400(self, client):
        from main import intents_db
        stale_id = "intent_expiredtest"
        intents_db[stale_id] = _stale_record(stale_id)
        # _fetch_or_404 auto-transitions status to "expired"; /verify returns 400
        r = client.post(f"/api/v1/intent/{stale_id}/verify", json=VERIFY_PAYLOAD)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# TestCompleteIntent
# ---------------------------------------------------------------------------

class TestCompleteIntent:
    """POST /api/v1/intent/{intent_id}/complete"""

    def test_complete_success_outcome(self, client, verified_intent):
        iid = verified_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/complete", json=COMPLETE_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["outcome"] == "fulfilled"
        assert data["audit_ready"] is True

    def test_complete_failure_outcome(self, client, verified_intent):
        iid = verified_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/complete", json={
            "reporter_id": "test-reporter",
            "outcome": "failed",
        })
        assert r.status_code == 200
        assert r.json()["outcome"] == "failed"
        assert r.json()["status"] == "completed"

    def test_complete_breach_detection(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        client.post(f"/api/v1/intent/{iid}/verify", json=VERIFY_PAYLOAD)
        # amount 9999 vs declared 100: 9899% deviation; currency "EUR" vs "USD"
        r = client.post(f"/api/v1/intent/{iid}/complete", json={
            "reporter_id": "auditor",
            "outcome": "disputed",
            "actual_details": {
                "target": "https://payment.example.com/pay",
                "amount": 9999,
                "currency": "EUR",
            },
        })
        assert r.status_code == 200
        breach = r.json()["breach_report"]
        assert breach["breach_detected"] is True
        assert breach["breach_count"] >= 1
        assert breach["severity"] in ("minor", "major")

    def test_complete_unverified_returns_400(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/complete", json=COMPLETE_PAYLOAD)
        assert r.status_code == 400

    def test_complete_nonexistent_returns_404(self, client):
        r = client.post("/api/v1/intent/intent_NONEXISTENT99/complete", json=COMPLETE_PAYLOAD)
        assert r.status_code == 404

    def test_complete_already_completed_returns_409(self, client, completed_intent):
        iid = completed_intent["intent_id"]
        r = client.post(f"/api/v1/intent/{iid}/complete", json=COMPLETE_PAYLOAD)
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# TestGetIntentStatus
# ---------------------------------------------------------------------------

class TestGetIntentStatus:
    """GET /api/v1/intent/{intent_id}"""

    def test_get_status_declared(self, client, declared_intent):
        iid = declared_intent["intent_id"]
        r = client.get(f"/api/v1/intent/{iid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        assert data["intent_id"] == iid
        assert data["binding_hash"] is None

    def test_get_status_verified(self, client, verified_intent):
        iid = verified_intent["intent_id"]
        r = client.get(f"/api/v1/intent/{iid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "verified"
        assert data["binding_hash"] is not None

    def test_get_status_completed(self, client, completed_intent):
        iid = completed_intent["intent_id"]
        r = client.get(f"/api/v1/intent/{iid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["audit_ready"] is True
        events = [e["event"] for e in data["audit_trail"]]
        assert "declared" in events
        assert "verified" in events
        assert "completed" in events

    def test_get_status_nonexistent_returns_404(self, client):
        assert client.get("/api/v1/intent/intent_NONEXISTENT99").status_code == 404

    def test_get_auto_expires_past_timeout(self, client):
        from main import intents_db
        stale_id = "intent_autoexpire0"
        intents_db[stale_id] = _stale_record(stale_id)
        r = client.get(f"/api/v1/intent/{stale_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "expired"


# ---------------------------------------------------------------------------
# TestRateLimiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Rate limit: 30 requests/minute/IP. _rate_store cleared by autouse fixture."""

    def test_under_limit_succeeds(self, client):
        for _ in range(5):
            assert client.get("/api/v1/intent/nonexistent").status_code == 404

    def test_over_limit_returns_429(self, client):
        for _ in range(30):
            client.get("/api/v1/intent/nonexistent")
        r = client.get("/api/v1/intent/nonexistent")  # 31st request — rate limited
        assert r.status_code == 429
        assert r.json()["status_code"] == 429

    def test_health_and_skill_md_exempt(self, client):
        for _ in range(30):
            client.get("/api/v1/intent/nonexistent")
        # API budget is exhausted, but discovery endpoints must still work
        assert client.get("/health").status_code == 200
        assert client.get("/SKILL.md").status_code == 200
