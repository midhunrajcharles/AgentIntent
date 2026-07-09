# AgentIntent — NandaHack Submission

Cryptographic intent declaration, verification, and audit for autonomous agents in the NANDA ecosystem.

An agent declares what it intends to do and receives a SHA-256 hash commitment. A counterparty
verifies the intent, producing a binding hash. After execution, the outcome is recorded and
compared against the declaration — breaches are detected automatically. Any third party can
audit the full lifecycle after the fact.

## Live Services

| Service | URL |
|---------|-----|
| AgentIntent API | https://agentintent.onrender.com |
| SKILL.md | https://agentintent.onrender.com/SKILL.md |
| API Docs | https://agentintent.onrender.com/docs |
| Payment Orchestrator | https://payment-orchestrator.onrender.com |
| Demo Page | https://YOUR_GITHUB_USERNAME.github.io/Nandahack-Agentintent/ |

## Quick Start (60 seconds)

```bash
BASE=https://agentintent.onrender.com

# 1. Declare an intent (returns intent_id + SHA-256 hash commitment)
INTENT_ID=$(curl -s -X POST $BASE/api/v1/intent/declare \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","intent_type":"authorize_payment","details":{"target":"https://payment.example.com/pay","amount":100,"currency":"USD"},"timeout_seconds":3600}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")

# 2. Verify it as the counterparty (produces a binding hash)
curl -s -X POST $BASE/api/v1/intent/$INTENT_ID/verify \
  -H "Content-Type: application/json" \
  -d '{"verifier_id":"auditor-001","accepts":true,"reason":"Matches PO-4421"}'

# 3. Record the outcome (breach detection compares it to the declaration)
curl -s -X POST $BASE/api/v1/intent/$INTENT_ID/complete \
  -H "Content-Type: application/json" \
  -d '{"reporter_id":"my-agent","outcome":"fulfilled","actual_details":{"target":"https://payment.example.com/pay","amount":100,"currency":"USD"}}'

# 4. Audit the full lifecycle
curl -s $BASE/api/v1/intent/$INTENT_ID
```

## Architecture

```
POST /api/v1/intent/declare        → register intent + SHA-256 hash commitment  (201)
POST /api/v1/intent/{id}/verify    → counterparty accepts/rejects → binding hash (200)
POST /api/v1/intent/{id}/complete  → record outcome + automatic breach detection (200)
GET  /api/v1/intent/{id}           → full audit trail                            (200)
```

State machine: `pending → verified → completed` (or `rejected` / `expired`, both terminal).

- **Storage:** In-memory dict (no database)
- **Proofs:** SHA-256 hash of canonical JSON (sorted keys — deterministic)
- **Auth:** None — open access for agents
- **Rate limit:** 30 requests/minute per IP (`/health`, `/SKILL.md`, `/docs` exempt)

## Project Structure

```
services/agentintent/          Main API service (FastAPI)
services/secure-payment-orchestrator/  Composability demo service
tests/                         pytest suite (judge simulation + API)
demo/index.html                GitHub Pages demo (no build required)
skills/                        Reference SKILL.md files
plans/EXECUTION_STATUS.md      Progress tracker
```

## Local Development

```bash
# Setup
bash scripts/setup.sh

# Run AgentIntent
cd services/agentintent
uvicorn main:app --reload --port 8000

# Run tests
pytest tests/ -v --cov=services/agentintent --cov-report=term-missing

# Open demo
open demo/index.html
```

## Scoring

| Category | Weight | Approach |
|----------|--------|---------|
| NANDA Town PR | 20% | Agent card + live URL |
| AgentIntent core | 40% | 4 clean endpoints, proper HTTP codes |
| SKILL.md quality | 40% | Judge simulation tests pass |
| Composability | +10% | Orchestrator calls AgentIntent via HTTP |

## Tech Stack

- Python 3.11 / FastAPI / Pydantic v2
- Deployment: Render (free tier)
- Testing: pytest + httpx
- Demo: Single HTML file (GitHub Pages)
