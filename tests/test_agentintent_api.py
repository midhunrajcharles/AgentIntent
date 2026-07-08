"""Full endpoint test suite for AgentIntent service."""
import pytest

VALID_PAYLOAD = {
    "agent_id": "agent-001",
    "action": "transfer_funds",
    "target": "https://payment.example.com/transfer",
    "parameters": {"amount": 100, "currency": "USD"},
    "ttl_seconds": 3600,
}


class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/api/v1/health").status_code == 200

    def test_status_healthy(self, client):
        assert client.get("/api/v1/health").json()["status"] == "healthy"

    def test_has_required_fields(self, client):
        data = client.get("/api/v1/health").json()
        for field in ["status", "service", "version", "timestamp", "intents_stored"]:
            assert field in data

    def test_intents_stored_is_int(self, client):
        assert isinstance(client.get("/api/v1/health").json()["intents_stored"], int)


class TestRegister:
    def test_returns_201(self, client):
        assert client.post("/api/v1/intents/register", json=VALID_PAYLOAD).status_code == 201

    def test_has_intent_id(self, client):
        data = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()
        assert "intent_id" in data and len(data["intent_id"]) > 0

    def test_proof_hash_is_64_chars(self, client):
        data = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()
        assert len(data["proof_hash"]) == 64

    def test_status_is_active(self, client):
        data = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()
        assert data["status"] == "active"

    def test_fields_match_request(self, client):
        data = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()
        assert data["agent_id"] == VALID_PAYLOAD["agent_id"]
        assert data["action"] == VALID_PAYLOAD["action"]
        assert data["target"] == VALID_PAYLOAD["target"]

    def test_unique_ids_per_call(self, client):
        id1 = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()["intent_id"]
        id2 = client.post("/api/v1/intents/register", json=VALID_PAYLOAD).json()["intent_id"]
        assert id1 != id2

    def test_missing_agent_id_422(self, client):
        p = {k: v for k, v in VALID_PAYLOAD.items() if k != "agent_id"}
        assert client.post("/api/v1/intents/register", json=p).status_code == 422

    def test_missing_action_422(self, client):
        p = {k: v for k, v in VALID_PAYLOAD.items() if k != "action"}
        assert client.post("/api/v1/intents/register", json=p).status_code == 422

    def test_missing_target_422(self, client):
        p = {k: v for k, v in VALID_PAYLOAD.items() if k != "target"}
        assert client.post("/api/v1/intents/register", json=p).status_code == 422

    def test_empty_body_422(self, client):
        assert client.post("/api/v1/intents/register", json={}).status_code == 422

    def test_default_ttl_accepted(self, client):
        p = {k: v for k, v in VALID_PAYLOAD.items() if k != "ttl_seconds"}
        assert client.post("/api/v1/intents/register", json=p).status_code == 201

    def test_optional_metadata(self, client):
        p = {**VALID_PAYLOAD, "metadata": {"source": "test"}}
        data = client.post("/api/v1/intents/register", json=p).json()
        assert data["metadata"] == {"source": "test"}

    def test_empty_parameters_accepted(self, client):
        p = {**VALID_PAYLOAD, "parameters": {}}
        assert client.post("/api/v1/intents/register", json=p).status_code == 201

    def test_ttl_too_low_422(self, client):
        p = {**VALID_PAYLOAD, "ttl_seconds": 10}
        assert client.post("/api/v1/intents/register", json=p).status_code == 422

    def test_ttl_too_high_422(self, client):
        p = {**VALID_PAYLOAD, "ttl_seconds": 999999}
        assert client.post("/api/v1/intents/register", json=p).status_code == 422


class TestGetIntent:
    def test_get_existing_200(self, client, registered_intent):
        r = client.get(f"/api/v1/intents/{registered_intent['intent_id']}")
        assert r.status_code == 200

    def test_get_returns_correct_data(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}").json()
        assert data["intent_id"] == registered_intent["intent_id"]
        assert data["agent_id"] == "test-agent"

    def test_get_nonexistent_404(self, client):
        assert client.get("/api/v1/intents/nonexistent123").status_code == 404

    def test_404_has_error_field(self, client):
        data = client.get("/api/v1/intents/nonexistent123").json()
        assert "error" in data or "detail" in data

    def test_get_includes_proof_hash(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}").json()
        assert "proof_hash" in data and len(data["proof_hash"]) == 64


class TestVerify:
    def test_verify_returns_200(self, client, registered_intent):
        r = client.get(f"/api/v1/intents/{registered_intent['intent_id']}/verify")
        assert r.status_code == 200

    def test_verify_valid_is_true(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}/verify").json()
        assert data["valid"] is True

    def test_verify_match_is_true(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}/verify").json()
        assert data["match"] is True

    def test_verify_hashes_equal(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}/verify").json()
        assert data["proof_hash"] == data["computed_hash"]

    def test_verify_nonexistent_404(self, client):
        assert client.get("/api/v1/intents/nonexistent123/verify").status_code == 404

    def test_verify_required_fields(self, client, registered_intent):
        data = client.get(f"/api/v1/intents/{registered_intent['intent_id']}/verify").json()
        for field in ["intent_id", "valid", "status", "proof_hash", "computed_hash", "match", "message"]:
            assert field in data, f"Missing: {field}"

    def test_verify_revoked_is_invalid(self, client, registered_intent):
        iid = registered_intent["intent_id"]
        client.delete(f"/api/v1/intents/{iid}")
        data = client.get(f"/api/v1/intents/{iid}/verify").json()
        assert data["valid"] is False


class TestRevoke:
    def test_revoke_returns_200(self, client, registered_intent):
        r = client.delete(f"/api/v1/intents/{registered_intent['intent_id']}")
        assert r.status_code == 200

    def test_revoke_changes_status(self, client, registered_intent):
        iid = registered_intent["intent_id"]
        client.delete(f"/api/v1/intents/{iid}")
        data = client.get(f"/api/v1/intents/{iid}").json()
        assert data["status"] == "revoked"

    def test_revoke_nonexistent_404(self, client):
        assert client.delete("/api/v1/intents/nonexistent123").status_code == 404

    def test_revoke_response_shape(self, client, registered_intent):
        data = client.delete(f"/api/v1/intents/{registered_intent['intent_id']}").json()
        assert data["status"] == "revoked"
        assert "message" in data
