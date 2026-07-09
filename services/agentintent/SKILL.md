---
name: AgentIntent
description: Cryptographic intent registration, verification, and audit for autonomous agents.
version: 1.0.0
base_url: https://agentintent.onrender.com
skill_url: https://agentintent.onrender.com/SKILL.md
tags: [intent, verification, audit, cryptography, trust, nanda]
auth: none
rate_limit: 30 requests/minute/IP
storage: in-memory (resets on restart)
---

# AgentIntent

## What This Does

AgentIntent gives autonomous agents a **tamper-proof paper trail for decisions before they
act**. An agent declares what it intends to do, receives a SHA-256 hash commitment, gets that
intent independently verified, executes its action, and records the outcome — all in a
three-step protocol with a cryptographic audit log at every stage.

The core guarantee: **any third party can independently verify, at any point after the fact,
exactly what an agent declared it would do, who approved it, and what actually happened** —
without trusting any single party's word. The `intent_hash` proves the declaration was not
modified after the fact. The `binding_hash` proves the verification decision was tied to a
specific intent. The `breach_report` proves whether the outcome matched the declaration.

This matters in multi-agent systems where one agent's action affects another agent's resources.
AgentIntent sits at the trust boundary between coordination, auth, and datafacts layers in
NANDA Town — providing the tamper-evident glue that makes multi-agent commitments auditable.

## When To Use This Skill

**Use AgentIntent when:**

- An agent needs tamper-proof proof of what it intended before it acted
- Two agents need to agree on a plan before either takes an action
- An orchestrator must verify a sub-agent's intent before authorising a resource action
- You need a cryptographically auditable decision log for autonomous actions
- You are building a NANDA scenario that touches coordination, auth, or datafacts layers

**Do NOT use AgentIntent when:**

- You need authentication or access control (this service is fully open — no API keys)
- You need persistent storage across restarts (in-memory only; seed a new intent each session)
- You need to *execute* actions (this records intentions, it does not act on them)
- You need real-time event streams (REST only, no webhooks or WebSockets)

---

## Quick Start — 4 Steps, Copy-Paste Ready

```bash
BASE=https://agentintent.onrender.com
```

Cold start note: Render free tier sleeps after 15 min. First request may take 20–30s. Retry 3x.

### Step 1 — Declare your intent

```bash
curl -s -X POST $BASE/api/v1/intent/declare \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id":    "buyer-agent-01",
    "intent_type": "purchase_token",
    "details": {
      "target":    "nanda://marketplace/tokens",
      "token_id":  "TOK-7821",
      "quantity":  10,
      "price_usd": 25.00
    },
    "max_cost":        250.00,
    "timeout_seconds": 1800
  }'
```

Save `intent_id` from the response — e.g. `"intent_abc123def456"`.

```bash
INTENT_ID=intent_abc123def456
```

### Step 2 — Verify the intent

```bash
curl -s -X POST $BASE/api/v1/intent/$INTENT_ID/verify \
  -H "Content-Type: application/json" \
  -d '{
    "verifier_id": "risk-engine-v2",
    "accepts":     true,
    "reason":      "Token purchase within approved budget",
    "conditions":  ["price_usd <= 30", "quantity <= 50"]
  }'
```

On acceptance the response includes `binding_hash` — the cryptographic commitment tying this
intent to this verification decision. Store it.

### Step 3 — Record the outcome

After executing the actual action:

```bash
curl -s -X POST $BASE/api/v1/intent/$INTENT_ID/complete \
  -H "Content-Type: application/json" \
  -d '{
    "reporter_id":    "buyer-agent-01",
    "outcome":        "fulfilled",
    "evidence_hash":  "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "actual_details": {
      "target":    "nanda://marketplace/tokens",
      "token_id":  "TOK-7821",
      "quantity":  10,
      "price_usd": 25.00
    }
  }'
```

The response contains a `breach_report` comparing declared vs actual details.

### Step 4 — Retrieve the full audit trail

```bash
curl -s $BASE/api/v1/intent/$INTENT_ID
```

`audit_ready: true` means the sealed, tamper-evident record is available.

---

## Demo Intent (No Registration Needed)

A demo intent is pre-loaded on every start:

```bash
curl -s $BASE/api/v1/intent/intent_demo000000
```

---

## Endpoint Reference

### GET /health

Liveness check. Always call this first. Retry after 20s if timeout (cold start).

```bash
curl -s $BASE/health
```

```json
{
  "status": "healthy", "service": "AgentIntent", "version": "1.0.0",
  "timestamp": "2026-07-08T14:32:00+00:00", "intents_stored": 1
}
```

---

### POST /api/v1/intent/declare → 201

Register an intent. Returns `intent_id` and `intent_hash`.

**Request:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `agent_id` | string | yes | 1–64 chars, `[a-zA-Z0-9][a-zA-Z0-9_.-]*` |
| `intent_type` | string | yes | 1–128 chars, `lower_snake_case` (`[a-z][a-z0-9_]*`) |
| `details` | object | no | JSON object; `target` key must be `https://`, `http://`, `nanda://`, or `df://` |
| `max_cost` | float | no | > 0, ≤ 1,000,000 |
| `timeout_seconds` | integer | no | 60–86400; default 3600 |

**Response 201:**

```json
{
  "intent_id":       "intent_abc123def456",
  "agent_id":        "buyer-agent-01",
  "intent_type":     "purchase_token",
  "status":          "pending",
  "intent_hash":     "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "created_at":      "2026-07-08T14:32:00+00:00",
  "expires_at":      "2026-07-08T14:62:00+00:00",
  "timeout_seconds": 1800,
  "max_cost":        250.00,
  "message":         "Intent declared. Submit to /verify before proceeding."
}
```

**Errors:** `422` — check `detail[0].loc[1]` for which field failed.

---

### POST /api/v1/intent/{intent_id}/verify → 200

Verify or reject a **pending** intent. Computes `binding_hash` on acceptance.

**Request:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `verifier_id` | string | yes | 1–64 chars, same pattern as `agent_id` |
| `accepts` | boolean | yes | `true` = approved; `false` = rejected |
| `reason` | string | no | Max 512 chars |
| `conditions` | array[string] | no | Max 20 entries |

**Response 200 — accepted:**

```json
{
  "intent_id":    "intent_abc123def456",
  "status":       "verified",
  "verified_by":  "risk-engine-v2",
  "accepted":     true,
  "binding_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
  "reason":       "Token purchase within approved budget",
  "verified_at":  "2026-07-08T14:33:00+00:00",
  "message":      "Intent verified. Binding commitment recorded. Proceed to /complete."
}
```

**Response 200 — rejected:**

```json
{
  "intent_id": "intent_abc123def456", "status": "rejected",
  "accepted": false, "binding_hash": null,
  "message": "Intent rejected by verifier. Declare a new intent to retry."
}
```

**Errors:** `404` not found | `400` expired | `409` wrong state (not pending).

---

### POST /api/v1/intent/{intent_id}/complete → 200

Record the final outcome of a **verified** intent. Runs breach detection.

**Request:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `reporter_id` | string | yes | 1–64 chars |
| `outcome` | string | yes | `"fulfilled"` / `"cancelled"` / `"failed"` / `"disputed"` |
| `evidence_hash` | string | no | 64-char SHA-256 hex |
| `actual_details` | object | no | Compared field-by-field against declared `details` |

**Response 200:**

```json
{
  "intent_id":  "intent_abc123def456",
  "status":     "completed",
  "outcome":    "fulfilled",
  "completed_at": "2026-07-08T14:35:00+00:00",
  "breach_report": {
    "breach_detected": false, "breaches": [], "breach_count": 0, "severity": "none"
  },
  "audit_trail": [
    {"event": "declared",  "timestamp": "...", "agent_id": "buyer-agent-01"},
    {"event": "verified",  "timestamp": "...", "verifier_id": "risk-engine-v2", "binding_hash": "..."},
    {"event": "completed", "timestamp": "...", "outcome": "fulfilled", "severity": "none"}
  ],
  "audit_ready": true,
  "message": "Intent completed with outcome 'fulfilled'. Breach severity: none."
}
```

**Errors:** `404` not found | `400` not in `verified` state | `409` already completed.

---

### GET /api/v1/intent/{intent_id} → 200

Retrieve current state and full metadata. Auto-expires if TTL elapsed.
`audit_ready` is `true` once `completed`, or when both hashes are present.

**Response 200:** (see full example above — all fields returned)

**Error:** `404` — intent_id unknown.

---

## Intent Lifecycle (State Machine)

```
POST /declare
      |
      v
  [pending]
      |
      +-- POST /verify (accepts=true)  --> [verified] --> POST /complete --> [completed]
      |
      +-- POST /verify (accepts=false) --> [rejected]   (terminal — declare new)
      |
      +-- TTL elapsed (auto-detected)  --> [expired]    (terminal — declare new)
```

| Status | `audit_ready` | Next action |
|---|---|---|
| `pending` | false | POST /verify |
| `verified` | false* | POST /complete |
| `rejected` | false | Declare new intent |
| `expired` | false | Declare new intent |
| `completed` | **true** | GET to retrieve sealed log |

*`audit_ready` becomes true once both `intent_hash` and `binding_hash` exist.

---

## Breach Detection Reference

`_detect_breach` compares every key in `details` (declared) against `actual_details` (reported).

| Comparison | Rule | Example breach |
|---|---|---|
| Numeric | 5% relative tolerance | `amount: 100` vs `amount: 200` = 100% deviation → breach |
| Numeric (OK) | Within tolerance | `amount: 100` vs `amount: 104` = 4% → no breach |
| String | Case-sensitive equality | `"USD"` vs `"EUR"` → breach |
| Omission | Field missing from actual | `details.vendor` not in `actual_details` → breach |
| Type | Python type must match | `true` (bool) vs `1` (int) → breach |

**Severity:** `"none"` = 0 breaches | `"minor"` = 1–2 | `"major"` = 3+

Extra keys in `actual_details` that were not in `details` are **ignored** (outcomes may legally
contain more information than the original declaration).

---

## Error Reference

| Code | Meaning | What to do |
|---|---|---|
| `200` / `201` | Success | Read response |
| `400` | Wrong state or expired | GET the intent first; declare new if expired |
| `404` | Not found | Check your `intent_id`; declare a new intent |
| `409` | State conflict | Read `detail` — intent already transitioned past this state |
| `422` | Validation failed | Fix field in `detail[0].loc[1]`; check pattern and type |
| `429` | Rate limited | Wait 60s; use back-off in production |
| `500` | Server error | Retry once after 5s; check /health |
| timeout | Cold start | Wait 20s, retry up to 3 times |

**Handling 422 — field validation error:**

```json
{
  "error": "Validation error",
  "detail": [{"type": "value_error", "loc": ["body", "details"],
               "msg": "Value error, details.target must start with one of: https://, ..."}],
  "status_code": 422
}
```

Read `detail[0].loc[1]` for the field name, `detail[0].msg` for the required fix.

---

## Advanced Patterns

### Conditional acceptance with conditions array

```json
{
  "verifier_id": "compliance-bot",
  "accepts": true,
  "reason": "Approved under Q3 budget policy",
  "conditions": ["amount <= 500.00", "currency == 'USD'", "vendor in approved_list"]
}
```

Conditions are stored in the audit trail for off-chain enforcement. AgentIntent records them
but does not enforce them — that is the verifier's responsibility.

### Multi-party sequential sign-off (off-chain)

Pass the `intent_id` to each approver. Each off-chain approver records its decision externally.
The final approver calls `/verify` with a `reason` that summarises the chain:

```json
{
  "verifier_id": "cfo-agent",
  "accepts": true,
  "reason": "Approved by risk-bot at 14:30Z and legal-bot at 14:31Z before CFO sign-off"
}
```

### Chaining with the Secure Payment Orchestrator

```bash
# 1. Declare payment intent
INTENT_ID=$(curl -s -X POST $BASE/api/v1/intent/declare \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"pay-bot","intent_type":"authorize_payment",
       "details":{"target":"https://payment.example.com","amount":99.99}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")

# 2. (Optional) Pre-verify before handing to orchestrator
curl -s -X POST $BASE/api/v1/intent/$INTENT_ID/verify \
  -H "Content-Type: application/json" \
  -d '{"verifier_id":"finance-approver","accepts":true}'

# 3. Pass to orchestrator — it calls GET /api/v1/intent/{id} before executing
curl -s -X POST https://secure-payment-orchestrator.vercel.app/api/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d "{\"intent_id\":\"$INTENT_ID\",\"action\":\"authorize_payment\",\"amount\":99.99}"
```

---

## Machine-Readable Agent Card

```json
{
  "service":      "AgentIntent",
  "version":      "1.0.0",
  "base_url":     "https://agentintent.onrender.com",
  "skill_url":    "https://agentintent.onrender.com/SKILL.md",
  "auth":         "none",
  "rate_limit":   "30 requests/minute/IP",
  "storage":      "in-memory",
  "demo_id":      "intent_demo000000",
  "workflow":     ["declare", "verify", "complete"],
  "endpoints": {
    "health":   "GET  /health",
    "declare":  "POST /api/v1/intent/declare",
    "verify":   "POST /api/v1/intent/{intent_id}/verify",
    "complete": "POST /api/v1/intent/{intent_id}/complete",
    "get":      "GET  /api/v1/intent/{intent_id}"
  },
  "statuses":     ["pending", "verified", "rejected", "expired", "completed"],
  "outcomes":     ["fulfilled", "cancelled", "failed", "disputed"],
  "hash_algo":    "SHA-256",
  "proof_fields": ["agent_id", "intent_type", "details"]
}
```

---

## Why This Exists

Autonomous agents in the NANDA ecosystem take consequential actions — publishing datasets,
initiating payments, bidding in auctions — without a human in the loop. When things go wrong,
it is very hard to reconstruct *what the agent intended*, *who approved it*, and *whether the
outcome matched the plan*.

AgentIntent creates a minimal, key-agnostic intent layer: no wallets, no smart contracts, no
authentication. Just a hash commitment that any party can compute from the public inputs,
verify against a stored record, and audit after the fact. The three-step protocol maps directly
to the trust layers in NANDA Town — providing the tamper-evident glue that makes multi-agent
commitments verifiable and composable.
