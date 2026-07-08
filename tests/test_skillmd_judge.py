"""
Judge simulation tests — mirrors exactly what a NandaHack judge agent does.
These MUST pass 100% for full SKILL.md score.
"""


class TestJudgeWorkflow:
    """Judge task sequence: health → register → retrieve → verify."""

    def test_task0_health_check(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_task1_register_intent(self, client):
        r = client.post("/api/v1/intents/register", json={
            "agent_id": "judge-agent",
            "action": "evaluate_submission",
            "target": "https://hackathon.nanda.ai/evaluate",
            "parameters": {"team": "NandaHackBot"},
        })
        assert r.status_code == 201
        data = r.json()
        assert "intent_id" in data
        assert data["status"] == "active"

    def test_task2_retrieve_intent(self, client):
        reg = client.post("/api/v1/intents/register", json={
            "agent_id": "judge-agent",
            "action": "retrieve_test",
            "target": "https://example.com",
            "parameters": {},
        }).json()
        r = client.get(f"/api/v1/intents/{reg['intent_id']}")
        assert r.status_code == 200
        assert r.json()["intent_id"] == reg["intent_id"]

    def test_task3_verify_proof(self, client):
        reg = client.post("/api/v1/intents/register", json={
            "agent_id": "judge-agent",
            "action": "verify_test",
            "target": "https://example.com",
            "parameters": {},
        }).json()
        r = client.get(f"/api/v1/intents/{reg['intent_id']}/verify")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["match"] is True

    def test_full_judge_sequence_end_to_end(self, client):
        # Health
        assert client.get("/api/v1/health").json()["status"] == "healthy"

        # Register
        reg_r = client.post("/api/v1/intents/register", json={
            "agent_id": "judge-full-test",
            "action": "full_sequence",
            "target": "https://nanda.ai/judge",
            "parameters": {"score": 100},
        })
        assert reg_r.status_code == 201
        intent = reg_r.json()
        iid = intent["intent_id"]

        # Retrieve
        get_r = client.get(f"/api/v1/intents/{iid}")
        assert get_r.status_code == 200
        assert get_r.json()["agent_id"] == "judge-full-test"

        # Verify
        ver_r = client.get(f"/api/v1/intents/{iid}/verify")
        assert ver_r.status_code == 200
        assert ver_r.json()["valid"] is True

    def test_judge_error_recovery_bad_id(self, client):
        r = client.get("/api/v1/intents/INVALID_JUDGE_ID_9999")
        assert r.status_code == 404
        data = r.json()
        assert "error" in data or "detail" in data

    def test_demo_intent_always_available(self, client):
        """Demo intent seeded at startup — judges can test without registering."""
        # Re-seed manually since store is cleared between tests
        from utils import store_intent
        from models import IntentRecord
        from utils import generate_proof_hash, build_proof_data
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        demo_id = "demo0000000001"
        proof_data = build_proof_data(demo_id, "demo-agent", "demo_action",
                                      "https://example.com", {"demo": True}, now)
        store_intent(IntentRecord(
            intent_id=demo_id,
            agent_id="demo-agent",
            action="demo_action",
            target="https://example.com",
            parameters={"demo": True},
            status="active",
            created_at=now,
            expires_at=now + timedelta(hours=24),
            proof_hash=generate_proof_hash(proof_data),
        ))
        r = client.get(f"/api/v1/intents/{demo_id}")
        assert r.status_code == 200


class TestJudgeEdgeCases:
    def test_register_with_all_optional_fields(self, client):
        r = client.post("/api/v1/intents/register", json={
            "agent_id": "edge-agent",
            "action": "edge_action",
            "target": "https://edge.example.com",
            "parameters": {"nested": {"key": "value"}, "list": [1, 2, 3]},
            "ttl_seconds": 7200,
            "metadata": {"env": "test", "version": 2},
        })
        assert r.status_code == 201

    def test_register_minimum_fields(self, client):
        r = client.post("/api/v1/intents/register", json={
            "agent_id": "min-agent",
            "action": "min_action",
            "target": "https://min.example.com",
        })
        assert r.status_code == 201

    def test_verify_after_revoke_shows_invalid(self, client):
        reg = client.post("/api/v1/intents/register", json={
            "agent_id": "revoke-test",
            "action": "test",
            "target": "https://example.com",
            "parameters": {},
        }).json()
        client.delete(f"/api/v1/intents/{reg['intent_id']}")
        ver = client.get(f"/api/v1/intents/{reg['intent_id']}/verify").json()
        assert ver["valid"] is False
        assert ver["status"] == "revoked"
