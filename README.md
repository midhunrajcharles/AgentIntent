# AgentIntent — NandaHack Submission

Cryptographic intent registration and verification for autonomous agents in the NANDA ecosystem.

## Live Services

| Service | URL |
|---------|-----|
| AgentIntent API | https://agentintent.onrender.com |
| SKILL.md | https://agentintent.onrender.com/SKILL.md |
| API Docs | https://agentintent.onrender.com/docs |
| Payment Orchestrator | https://payment-orchestrator.onrender.com |
| Demo Page | https://YOUR_GITHUB_USERNAME.github.io/Nandahack-Agentintent/ |

## Quick Start (30 seconds)

```bash
BASE=https://agentintent.onrender.com

# Register an intent
curl -s -X POST $BASE/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my-agent","action":"fetch_data","target":"https://api.example.com","parameters":{}}'

# Verify it (replace INTENT_ID)
curl -s $BASE/api/v1/intents/INTENT_ID/verify
```

## Architecture

```
POST /api/v1/intents/register   → creates intent + SHA256 proof
GET  /api/v1/intents/{id}       → retrieve intent
GET  /api/v1/intents/{id}/verify → verify cryptographic proof
DELETE /api/v1/intents/{id}     → revoke intent
```

- **Storage:** In-memory dict (no database)
- **Proofs:** SHA-256 hash of canonical JSON
- **Auth:** None — open access for agents
- **Rate limit:** 60 requests/minute per IP

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
