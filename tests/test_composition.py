"""
Composability tests — verify the orchestrator calls AgentIntent correctly.
Uses httpx mocking so no live services required.
"""
import sys
import os
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "secure-payment-orchestrator"))

import main as orch_main

MOCK_VERIFY_VALID = {
    "intent_id": "abc123",
    "valid": True,
    "status": "active",
    "proof_hash": "aaa",
    "computed_hash": "aaa",
    "match": True,
    "message": "Intent verified successfully",
}

MOCK_VERIFY_INVALID = {
    "intent_id": "abc123",
    "valid": False,
    "status": "active",
    "proof_hash": "aaa",
    "computed_hash": "bbb",
    "match": False,
    "message": "Proof hash mismatch",
}


@pytest.fixture
def orch_client():
    return TestClient(orch_main.app)


class TestOrchestratorHealth:
    def test_health_200(self, orch_client):
        assert orch_client.get("/api/v1/health").status_code == 200

    def test_health_fields(self, orch_client):
        data = orch_client.get("/api/v1/health").json()
        assert data["status"] == "healthy"
        assert "agentintent_base" in data


class TestOrchestratorCompose:
    def _mock_verify(self, status_code: int, body: dict):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = body
        return mock_resp

    def test_authorized_when_intent_valid(self, orch_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = \
                self._mock_verify(200, MOCK_VERIFY_VALID)
            r = orch_client.post("/api/v1/orchestrate", json={
                "intent_id": "abc123",
                "action": "authorize_payment",
                "amount": 99.99,
            })
        assert r.status_code == 200
        data = r.json()
        assert data["intent_verified"] is True
        assert data["payment_status"] == "authorized"
        assert data["transaction_id"] != "NONE"

    def test_rejected_when_intent_invalid(self, orch_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = \
                self._mock_verify(200, MOCK_VERIFY_INVALID)
            r = orch_client.post("/api/v1/orchestrate", json={
                "intent_id": "abc123",
                "action": "authorize_payment",
                "amount": 50.0,
            })
        assert r.status_code == 200
        data = r.json()
        assert data["intent_verified"] is False
        assert data["payment_status"] == "rejected"
        assert data["transaction_id"] == "NONE"

    def test_404_when_intent_not_found(self, orch_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = \
                self._mock_verify(404, {"error": "not found"})
            r = orch_client.post("/api/v1/orchestrate", json={
                "intent_id": "nonexistent",
                "action": "test",
                "amount": 10.0,
            })
        assert r.status_code == 404

    def test_502_when_agentintent_unreachable(self, orch_client):
        with patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = \
                httpx.ConnectError("Connection refused")
            r = orch_client.post("/api/v1/orchestrate", json={
                "intent_id": "abc123",
                "action": "test",
                "amount": 10.0,
            })
        assert r.status_code == 502

    def test_amount_too_high_422(self, orch_client):
        r = orch_client.post("/api/v1/orchestrate", json={
            "intent_id": "abc123",
            "action": "test",
            "amount": 99999.0,
        })
        assert r.status_code == 422

    def test_missing_intent_id_422(self, orch_client):
        r = orch_client.post("/api/v1/orchestrate", json={
            "action": "test",
            "amount": 10.0,
        })
        assert r.status_code == 422
