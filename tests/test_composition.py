"""
Composability tests — verify the orchestrator calls AgentIntent correctly.
Orchestrator calls GET /api/v1/intent/{id}; statuses pending/verified = authorized.
"""
import importlib.util
import pathlib
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Load orchestrator main via explicit path to avoid module-name collision.
_orch_path = pathlib.Path(__file__).parent.parent / "services" / "secure-payment-orchestrator" / "main.py"
_spec = importlib.util.spec_from_file_location("orch_main", _orch_path)
orch_main = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(orch_main)  # type: ignore[union-attr]

# Canned GET /api/v1/intent/{id} responses
_INTENT_PENDING = {
    "intent_id": "intent_abc123def456",
    "agent_id": "test-agent",
    "intent_type": "authorize_payment",
    "details": {"target": "https://payment.example.com", "amount": 99.99},
    "status": "pending",
    "intent_hash": "a" * 64,
    "binding_hash": None,
    "audit_ready": False,
}
_INTENT_VERIFIED = {**_INTENT_PENDING, "status": "verified", "binding_hash": "b" * 64, "audit_ready": True}
_INTENT_REJECTED = {**_INTENT_PENDING, "status": "rejected"}
_INTENT_EXPIRED = {**_INTENT_PENDING, "status": "expired"}
_INTENT_COMPLETED = {**_INTENT_PENDING, "status": "completed", "audit_ready": True}

_ORCHESTRATE_PAYLOAD = {
    "intent_id": "intent_abc123def456",
    "action": "authorize_payment",
    "amount": 99.99,
}


@pytest.fixture
def orch_client():
    return TestClient(orch_main.app)


def _mock_get(status_code: int, body: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    return resp


class TestOrchestratorHealth:
    def test_health_200(self, orch_client):
        assert orch_client.get("/api/v1/health").status_code == 200

    def test_health_fields(self, orch_client):
        data = orch_client.get("/api/v1/health").json()
        assert data["status"] == "healthy"
        assert "agentintent_base" in data


class TestOrchestratorCompose:
    def test_authorized_when_intent_pending(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = _mock_get(200, _INTENT_PENDING)
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert data["intent_verified"] is True
        assert data["payment_status"] == "authorized"
        assert data["transaction_id"] != "NONE"

    def test_authorized_when_intent_verified(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = _mock_get(200, _INTENT_VERIFIED)
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 200
        assert r.json()["payment_status"] == "authorized"

    def test_rejected_when_intent_rejected(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = _mock_get(200, _INTENT_REJECTED)
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 200
        data = r.json()
        assert data["intent_verified"] is False
        assert data["payment_status"] == "rejected"
        assert data["transaction_id"] == "NONE"

    def test_rejected_when_intent_expired(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = _mock_get(200, _INTENT_EXPIRED)
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 200
        assert r.json()["payment_status"] == "rejected"

    def test_404_when_intent_not_found(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = _mock_get(404, {"error": "not found"})
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 404

    def test_502_when_agentintent_unreachable(self, orch_client):
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("refused")
            r = orch_client.post("/api/v1/orchestrate", json=_ORCHESTRATE_PAYLOAD)
        assert r.status_code == 502

    def test_amount_too_high_422(self, orch_client):
        r = orch_client.post("/api/v1/orchestrate", json={**_ORCHESTRATE_PAYLOAD, "amount": 99999.0})
        assert r.status_code == 422

    def test_missing_intent_id_422(self, orch_client):
        r = orch_client.post("/api/v1/orchestrate", json={"action": "test", "amount": 10.0})
        assert r.status_code == 422
