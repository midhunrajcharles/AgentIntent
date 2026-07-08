# AgentIntent Service — SKILL.md
**Base URL:** https://agentintent.onrender.com  
**Version:** 1.0.0  
**Auth:** None — open access  
**Format:** JSON (`Content-Type: application/json` for POST requests)

---

## Quick Start (3 calls, copy-paste ready)

```bash
BASE=https://agentintent.onrender.com

# 1. Register an intent — save the intent_id from the response
curl -s -X POST $BASE/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent-001",
    "action": "fetch_weather",
    "target": "https://weather.api.com/current",
    "parameters": {"city": "New York"},
    "ttl_seconds": 3600
  }'

# 2. Retrieve the intent (replace INTENT_ID)
curl -s $BASE/api/v1/intents/INTENT_ID

# 3. Verify the cryptographic proof
curl -s $BASE/api/v1/intents/INTENT_ID/verify
# → {"valid": true, "match": true, ...}
```

A demo intent is always available at:
```bash
curl -s $BASE/api/v1/intents/demo0000000001
curl -s $BASE/api/v1/intents/demo0000000001/verify
```

---

## Endpoints

### GET /api/v1/health
Service liveness check. Call this first; retry after 15s if the service is cold-starting.

```json
{"status": "healthy", "service": "AgentIntent", "version": "1.0.0", "timestamp": "...", "intents_stored": 1}
```

---

### POST /api/v1/intents/register → 201
Register a new intent. Returns `intent_id` — needed for all subsequent calls.

**Request fields:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| agent_id | string | yes | 1–64 chars | Your agent's unique ID |
| action | string | yes | 1–128 chars | Intended action |
| target | string | yes | non-empty | Target resource/URL |
| parameters | object | no | any key-values | Action parameters |
| ttl_seconds | integer | no | 60–86400, default 3600 | Intent lifetime |
| metadata | object | no | any | Extra info |

**Response 201:**
```json
{
  "intent_id": "a3f7b2c1d4e5ab12",
  "agent_id": "my-agent-001",
  "action": "fetch_weather",
  "target": "https://weather.api.com/current",
  "parameters": {"city": "New York"},
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T11:30:00Z",
  "proof_hash": "e3b0c44298fc1c149afbf4c8996fb924...",
  "metadata": null
}
```

**Errors:**
- `422` — Missing required field or wrong type. Check field constraints above.
- `429` — Rate limit (60 req/min). Wait 60s and retry.

---

### GET /api/v1/intents/{intent_id} → 200
Retrieve a registered intent by its ID.

**Response 200:** Same shape as register response above.

**Response 404:**
```json
{"error": "Intent not found", "detail": "No intent with ID 'xyz'", "status_code": 404}
```
If 404: the intent may have expired. Register a new one.

---

### GET /api/v1/intents/{intent_id}/verify → 200
Cryptographically verify an intent's proof hash (SHA-256).

**Response 200:**
```json
{
  "intent_id": "a3f7b2c1d4e5ab12",
  "valid": true,
  "status": "active",
  "proof_hash": "e3b0c44298fc1c...",
  "computed_hash": "e3b0c44298fc1c...",
  "match": true,
  "message": "Intent verified successfully"
}
```

**Interpret results:**
- `valid: true, match: true` → Authentic and active ✓
- `valid: false, match: false` → Tampered or corrupted ✗
- `valid: false, match: true` → Hash OK but intent is expired/revoked

---

### DELETE /api/v1/intents/{intent_id} → 200
Revoke an intent (soft delete — record kept, status set to `revoked`).

**Response 200:**
```json
{"intent_id": "a3f7b2c1d4e5ab12", "status": "revoked", "message": "Intent revoked successfully"}
```

---

## Error Reference

| Code | Meaning | What to do |
|------|---------|-----------|
| 200 | Success | Proceed |
| 201 | Intent created | Save `intent_id` |
| 404 | Not found | Register a new intent |
| 422 | Validation error | Fix request fields |
| 429 | Rate limited | Wait 60s, retry |
| 500 | Server error | Retry once; check /health |
| timeout | Cold start | Wait 15s, retry up to 3× |

---

## Cold Start
Render free tier sleeps after 15 min inactivity. First request may take 20–30s.  
Retry strategy: wait 15s between attempts, max 3 retries.

---

## Composability
Chain with the **Secure Payment Orchestrator** service:
- Register an intent here → pass `intent_id` to the orchestrator
- Orchestrator verifies the intent before executing any payment action
- Orchestrator SKILL.md: `https://payment-orchestrator.onrender.com/SKILL_ORCH.md`

Example chain:
```bash
# 1. Register intent
INTENT_ID=$(curl -s -X POST $BASE/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"orch-agent","action":"authorize_payment","target":"https://payment.example.com","parameters":{"amount":50}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")

# 2. Pass to orchestrator
curl -s -X POST https://payment-orchestrator.onrender.com/api/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d "{\"intent_id\": \"$INTENT_ID\", \"action\": \"authorize_payment\", \"amount\": 50}"
```
