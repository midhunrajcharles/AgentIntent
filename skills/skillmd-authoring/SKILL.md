# SKILL: Writing Perfect SKILL.md Files

## PURPOSE
Create SKILL.md files that allow any AI agent to discover, understand, and successfully call a service with zero human assistance. SKILL.md is worth 40% of the NandaHack score.

---

## WHAT A PERFECT SKILL.md ACHIEVES

A judge will simulate an AI agent who:
1. Has never seen your service before
2. Reads SKILL.md as the sole source of truth
3. Must complete 3 tasks: register an intent, retrieve it, verify it
4. Must handle the case where the service is cold-started (Render free tier sleeps)

**Your SKILL.md passes if the agent succeeds at all 3 tasks on first attempt.**

---

## REQUIRED SECTIONS (in order)

### 1. Header Block (5 lines max)
```markdown
# AgentIntent Service — SKILL.md
**Base URL:** https://agentintent.onrender.com  
**Version:** 1.0.0  
**Auth:** None required  
**Format:** All requests/responses are JSON
```

### 2. Quick Start (the single most important section)
Must contain ONE working example that goes start-to-finish. An agent that only reads this section should still succeed.

```markdown
## Quick Start
# Step 1: Register an intent
curl -X POST https://agentintent.onrender.com/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","action":"do_task","target":"https://example.com","parameters":{}}'
# → Returns: {"intent_id": "abc123def456", ...}

# Step 2: Retrieve it
curl https://agentintent.onrender.com/api/v1/intents/abc123def456

# Step 3: Verify it
curl https://agentintent.onrender.com/api/v1/intents/abc123def456/verify
# → Returns: {"valid": true, "match": true, ...}
```

### 3. Endpoint Reference
For EACH endpoint, provide:
- Method + path
- One-line description
- Full request schema with types
- Full response schema with example values
- All possible error responses

### 4. Field Definitions
Define every field that appears in requests or responses. Do not assume the agent knows what `proof_hash` means.

### 5. Error Handling Guide
List every error code. Tell the agent exactly what to do when it receives each one.

### 6. Cold Start Notice
```markdown
## Cold Start Warning
This service runs on Render free tier. If the first request times out (>30s),
wait 10 seconds and retry. The service auto-wakes on first request.
```

### 7. Composability Section
Explain how another agent or service can chain with this one.

---

## ANTI-PATTERNS TO AVOID

### Bad: Vague description
```markdown
## Register Intent
POST to the register endpoint with your intent data.
```

### Good: Precise, executable
```markdown
## POST /api/v1/intents/register
Register a new agent intent. Returns intent_id needed for all subsequent calls.

Request body (all fields required unless marked optional):
- agent_id (string, 1-64 chars): Your agent's unique identifier
- action (string, 1-128 chars): What your agent intends to do
- target (string, valid URL): The resource your agent will act on
- parameters (object, optional): Key-value pairs for the action
- ttl_seconds (integer, 60-86400, default 3600): How long intent stays active

Returns 201 on success. The intent_id field is your handle for all future calls.
```

---

## FULL SKILL.md TEMPLATE FOR AGENTINTENT

```markdown
# AgentIntent Service — SKILL.md
**Base URL:** https://agentintent.onrender.com  
**Version:** 1.0.0  
**Auth:** None — open access for agents  
**Format:** JSON (Content-Type: application/json for all POST requests)

---

## Quick Start (Complete in 3 calls)

### 1. Register an intent
\`\`\`bash
curl -X POST https://agentintent.onrender.com/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent-001",
    "action": "fetch_weather",
    "target": "https://weather.api.com/current",
    "parameters": {"city": "New York"},
    "ttl_seconds": 3600
  }'
\`\`\`
**Save the `intent_id` from the response.**

### 2. Retrieve the intent
\`\`\`bash
curl https://agentintent.onrender.com/api/v1/intents/{intent_id}
\`\`\`

### 3. Verify cryptographic proof
\`\`\`bash
curl https://agentintent.onrender.com/api/v1/intents/{intent_id}/verify
\`\`\`
If `"valid": true` and `"match": true` — the intent is authentic and unmodified.

---

## Endpoints

### GET /api/v1/health
Check service status. Always call this first.

Response 200:
\`\`\`json
{"status": "healthy", "service": "AgentIntent", "version": "1.0.0", "intents_stored": 3}
\`\`\`

---

### POST /api/v1/intents/register
Register a new intent. Returns a unique intent_id and cryptographic proof.

Request fields:
| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| agent_id | string | yes | 1-64 chars | Your agent's ID |
| action | string | yes | 1-128 chars | What you intend to do |
| target | string | yes | any string | Target resource |
| parameters | object | no | any key-values | Action parameters |
| ttl_seconds | integer | no | 60-86400, default 3600 | Lifetime |
| metadata | object | no | any | Extra info |

Response 201:
\`\`\`json
{
  "intent_id": "a3f7b2c1d4e5",
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
\`\`\`

Errors:
- 422: Missing required field or invalid type — check field constraints above
- 429: Rate limit (60/min) — wait 60s and retry

---

### GET /api/v1/intents/{intent_id}
Retrieve a previously registered intent.

Path parameter: `intent_id` — the 12-character hex ID from registration

Response 200: Same shape as register response above
Response 404: `{"error": "Intent not found", "detail": "...", "status_code": 404}`

If you receive 404, the intent may have expired. Register a new one.

---

### GET /api/v1/intents/{intent_id}/verify
Cryptographically verify an intent's proof hash.

Response 200:
\`\`\`json
{
  "intent_id": "a3f7b2c1d4e5",
  "valid": true,
  "status": "active",
  "proof_hash": "e3b0c44298fc1c...",
  "computed_hash": "e3b0c44298fc1c...",
  "match": true,
  "message": "Intent verified successfully"
}
\`\`\`

Interpret results:
- `"valid": true, "match": true` → Intent is authentic and active ✓
- `"valid": false, "match": false` → Proof hash mismatch — data tampered ✗
- `"valid": false, "match": true` → Hash matches but intent expired or revoked

---

### DELETE /api/v1/intents/{intent_id}
Revoke an intent. The record is kept but marked as revoked.

Response 200:
\`\`\`json
{"intent_id": "a3f7b2c1d4e5", "status": "revoked", "message": "Intent revoked successfully"}
\`\`\`

---

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| 404 | Intent not found | Register a new intent |
| 422 | Validation error | Check required fields and types |
| 429 | Rate limited | Wait 60 seconds, retry |
| 500 | Server error | Retry once; if persistent, check /health |
| timeout | Service cold start | Wait 15 seconds, retry |

---

## Cold Start
Service sleeps after 15 min inactivity (Render free tier).
First request may take 20-30s. Retry logic: wait 15s, retry up to 3 times.

---

## Composability
This service can be chained with the AgentVerifierBot:
- Register intent here → pass `intent_id` to VerifierBot
- VerifierBot URL: https://agentverifier.onrender.com
- VerifierBot SKILL.md: https://agentverifier.onrender.com/SKILL.md
```

---

## JUDGE SIMULATION CHECKLIST

Before submitting, run through this as if you are the judge agent:

- [ ] Can I find the Base URL in under 5 seconds of reading?
- [ ] Can I register an intent by copy-pasting from Quick Start?
- [ ] Do I know what `intent_id` is and where to find it in the response?
- [ ] Can I retrieve the intent without guessing any field names?
- [ ] Can I verify the intent and interpret the result without ambiguity?
- [ ] Do I know what to do if I get a 404?
- [ ] Do I know what to do if the service is slow (cold start)?
- [ ] Can I find the composability hook for a second service?

If any answer is "no" — revise before submitting.
