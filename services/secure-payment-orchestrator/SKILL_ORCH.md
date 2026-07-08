# Secure Payment Orchestrator — SKILL_ORCH.md
**Base URL:** https://payment-orchestrator.onrender.com  
**Version:** 1.0.0  
**Auth:** None  
**Depends on:** AgentIntent Service at https://agentintent.onrender.com

---

## Purpose
This service executes payment actions **only after** verifying a cryptographic intent proof
from the AgentIntent service. It demonstrates cross-service composability.

---

## Quick Start

```bash
ORCH=https://payment-orchestrator.onrender.com
AI=https://agentintent.onrender.com

# Step 1: Register intent with AgentIntent
INTENT_ID=$(curl -s -X POST $AI/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"orch-demo","action":"authorize_payment","target":"https://payment.example.com","parameters":{"amount":99.99}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")

echo "Intent ID: $INTENT_ID"

# Step 2: Orchestrate payment (orchestrator verifies intent automatically)
curl -s -X POST $ORCH/api/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d "{\"intent_id\": \"$INTENT_ID\", \"action\": \"authorize_payment\", \"amount\": 99.99, \"recipient\": \"vendor@example.com\"}"
```

---

## Endpoints

### GET /api/v1/health → 200
```json
{"status": "healthy", "service": "SecurePaymentOrchestrator", "agentintent_base": "..."}
```

### POST /api/v1/orchestrate → 200
Verify intent and execute payment action.

**Request:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| intent_id | string | yes | from AgentIntent register |
| action | string | yes | payment action name |
| amount | float | yes | 0.01–10000 USD |
| recipient | string | no | default: mock-recipient@example.com |

**Response 200 (authorized):**
```json
{
  "intent_id": "a3f7b2c1d4e5ab12",
  "action": "authorize_payment",
  "amount": 99.99,
  "recipient": "vendor@example.com",
  "intent_verified": true,
  "payment_status": "authorized",
  "transaction_id": "tx_abc123def456",
  "timestamp": "2024-01-15T10:31:00Z",
  "message": "Payment authorized via verified intent"
}
```

**Response 200 (rejected — invalid intent):**
```json
{
  "intent_verified": false,
  "payment_status": "rejected",
  "transaction_id": "NONE",
  "message": "Payment rejected: intent verification failed"
}
```

**Errors:**
- `404` — Intent ID not found in AgentIntent
- `502` — AgentIntent service unreachable
- `504` — AgentIntent timeout (cold start) — wait 15s and retry

---

## Composability Flow

```
Agent
  │
  ├─ POST /api/v1/intents/register  →  AgentIntent  (gets intent_id)
  │
  └─ POST /api/v1/orchestrate       →  Orchestrator
                                           │
                                           └─ GET /intents/{id}/verify  →  AgentIntent
                                                      │
                                           authorized or rejected  →  Agent
```

---

## Cold Start
Both services may sleep on Render free tier. If you get a timeout:
1. GET `https://agentintent.onrender.com/api/v1/health` — wait for 200
2. GET `https://payment-orchestrator.onrender.com/api/v1/health` — wait for 200
3. Retry orchestrate call
