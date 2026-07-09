"""
Judge simulation tests — mirrors exactly what a NandaHack judge agent does.
Follows the 3-step workflow: declare → verify → complete.
All tests MUST pass 100% for full SKILL.md score.
"""
from conftest import DECLARE_PAYLOAD, VERIFY_PAYLOAD, COMPLETE_PAYLOAD


class TestJudgeWorkflow:
    """Judge task sequence: health → declare → verify → complete → get."""

    def test_task0_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_task1_declare_intent(self, client):
        r = client.post("/api/v1/intent/declare", json={
            "agent_id": "judge-agent",
            "intent_type": "evaluate_submission",
            "details": {
                "target": "https://hackathon.nanda.ai/evaluate",
                "team": "NandaHackBot",
            },
        })
        assert r.status_code == 201
        data = r.json()
        assert data["intent_id"].startswith("intent_")
        assert data["status"] == "pending"
        assert len(data["intent_hash"]) == 64

    def test_task2_verify_intent(self, client):
        reg = client.post("/api/v1/intent/declare", json={
            "agent_id": "judge-agent",
            "intent_type": "verify_submission",
            "details": {"target": "https://nanda.ai/verify"},
        }).json()
        r = client.post(f"/api/v1/intent/{reg['intent_id']}/verify", json={
            "verifier_id": "judge-auditor",
            "accepts": True,
            "reason": "Submission criteria met",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "verified"
        assert data["accepted"] is True
        assert len(data["binding_hash"]) == 64

    def test_task3_complete_intent(self, client):
        reg = client.post("/api/v1/intent/declare", json={
            "agent_id": "judge-agent",
            "intent_type": "score_submission",
            "details": {"target": "https://nanda.ai/score", "team": "NandaHackBot"},
        }).json()
        client.post(f"/api/v1/intent/{reg['intent_id']}/verify", json={
            "verifier_id": "judge-auditor",
            "accepts": True,
        })
        r = client.post(f"/api/v1/intent/{reg['intent_id']}/complete", json={
            "reporter_id": "judge-agent",
            "outcome": "fulfilled",
            "actual_details": {"team": "NandaHackBot"},
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["audit_ready"] is True

    def test_task4_get_audit_trail(self, client):
        # Full flow, then retrieve and inspect
        reg = client.post("/api/v1/intent/declare", json={
            "agent_id": "judge-agent",
            "intent_type": "audit_trail_test",
            "details": {"target": "https://nanda.ai/audit"},
        }).json()
        iid = reg["intent_id"]
        client.post(f"/api/v1/intent/{iid}/verify", json={"verifier_id": "j", "accepts": True})
        client.post(f"/api/v1/intent/{iid}/complete", json={
            "reporter_id": "judge-agent",
            "outcome": "fulfilled",
            "actual_details": {},
        })
        r = client.get(f"/api/v1/intent/{iid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["audit_ready"] is True
        events = [e["event"] for e in data["audit_trail"]]
        assert "declared" in events
        assert "verified" in events
        assert "completed" in events

    def test_full_judge_sequence_end_to_end(self, client):
        # Health
        assert client.get("/health").json()["status"] == "healthy"

        # Declare
        reg_r = client.post("/api/v1/intent/declare", json={
            "agent_id": "judge-full-test",
            "intent_type": "full_sequence",
            "details": {"target": "https://nanda.ai/judge", "score": 100},
        })
        assert reg_r.status_code == 201
        iid = reg_r.json()["intent_id"]

        # Verify
        ver_r = client.post(f"/api/v1/intent/{iid}/verify", json={
            "verifier_id": "auditor-judge",
            "accepts": True,
            "reason": "All criteria satisfied",
        })
        assert ver_r.status_code == 200
        assert ver_r.json()["status"] == "verified"

        # Complete
        cmp_r = client.post(f"/api/v1/intent/{iid}/complete", json={
            "reporter_id": "judge-full-test",
            "outcome": "fulfilled",
            "actual_details": {"score": 100},
        })
        assert cmp_r.status_code == 200
        assert cmp_r.json()["audit_ready"] is True

        # Retrieve final state
        get_r = client.get(f"/api/v1/intent/{iid}")
        assert get_r.status_code == 200
        assert get_r.json()["status"] == "completed"

    def test_judge_error_recovery_bad_id(self, client):
        r = client.get("/api/v1/intent/intent_INVALID_9999")
        assert r.status_code == 404
        data = r.json()
        assert "error" in data or "detail" in data

    def test_demo_intent_always_available(self, client, demo_intent):
        r = client.get("/api/v1/intent/intent_demo000000")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"


class TestJudgeEdgeCases:
    def test_declare_with_all_optional_fields(self, client):
        r = client.post("/api/v1/intent/declare", json={
            "agent_id": "edge-agent",
            "intent_type": "edge_action",
            "details": {
                "target": "https://edge.example.com",
                "nested": {"key": "value"},
                "list": [1, 2, 3],
            },
            "max_cost": 250.0,
            "timeout_seconds": 7200,
        })
        assert r.status_code == 201

    def test_declare_minimum_fields(self, client):
        r = client.post("/api/v1/intent/declare", json={
            "agent_id": "min-agent",
            "intent_type": "min_action",
            "details": {"action": "test"},
        })
        assert r.status_code == 201

    def test_verify_then_complete_shows_no_breach(self, client):
        reg = client.post("/api/v1/intent/declare", json={
            "agent_id": "breach-test",
            "intent_type": "test_no_breach",
            "details": {"target": "https://example.com", "amount": 100},
        }).json()
        iid = reg["intent_id"]
        client.post(f"/api/v1/intent/{iid}/verify", json={"verifier_id": "v", "accepts": True})
        # actual_details must match declared details (including target) for no breach
        data = client.post(f"/api/v1/intent/{iid}/complete", json={
            "reporter_id": "breach-test",
            "outcome": "fulfilled",
            "actual_details": {"target": "https://example.com", "amount": 100},
        }).json()
        assert data["breach_report"]["breach_detected"] is False

    def test_reject_then_cannot_complete(self, client):
        reg = client.post("/api/v1/intent/declare", json={
            "agent_id": "reject-test",
            "intent_type": "test_reject",
            "details": {"target": "https://example.com"},
        }).json()
        iid = reg["intent_id"]
        client.post(f"/api/v1/intent/{iid}/verify", json={"verifier_id": "v", "accepts": False})
        assert client.post(f"/api/v1/intent/{iid}/complete", json=COMPLETE_PAYLOAD).status_code == 400
