# SKILL: NandaHack Competition Rules & Scoring

## PURPOSE
Understand and apply the complete NandaHack competition rules to maximize score across all judging criteria.

## COMPETITION OVERVIEW
NandaHack is an AI agent interoperability hackathon focused on the NANDA (Networked Agents for Decentralized Autonomy) ecosystem. The goal is to build an AgentIntent service that any autonomous agent can discover, understand, and call without human assistance.

---

## SCORING BREAKDOWN (Total: 100 points)

### 1. NANDA Town Integration (20 points)
- Submit a Pull Request to the NANDA Town registry
- PR must include: agent card JSON, SKILL.md reference, live HTTPS URL
- Agent card must be valid JSON conforming to NANDA schema
- Live endpoint must respond within 5 seconds

**How to maximize:**
- Submit PR early (bonus points for early submission)
- Agent card must have all required fields: `name`, `description`, `skill_url`, `endpoints`
- HTTPS URL must be reachable from judge's machine (use Render free tier)

### 2. AgentIntent Core Service (40 points)
- Build the main AgentIntent API service
- Must have at minimum 2, maximum 4 endpoints
- All endpoints must return structured JSON
- Must demonstrate intent registration, retrieval, and verification

**Scoring sub-criteria:**
- Endpoint correctness: 15 points
- Response format quality: 10 points
- Error handling: 10 points
- Performance (<500ms p99): 5 points

### 3. SKILL.md Quality (40 points)
- The SKILL.md file is the primary interface for AI agents
- Judges simulate an AI agent following SKILL.md instructions
- Agent must succeed at all 3 judge tasks using only SKILL.md

**Scoring sub-criteria:**
- Discoverability (agent can find the skill): 10 points
- Executability (agent can call endpoints): 15 points
- Composability (agent can chain with other services): 10 points
- Error recovery (agent handles failures): 5 points

### 4. Composability Bonus (10 points extra credit)
- Build a second service that calls the first via HTTP
- Demonstrate agent orchestration across 2+ services
- Both services must be live on HTTPS

---

## TIMELINE

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | Hours 1-2 | NANDA Town PR submitted |
| Phase 2 | Hours 3-8 | AgentIntent service live on Render |
| Phase 3 | Hours 9-10 | SKILL.md polished, composability demo |
| Phase 4 | Hours 11-12 | Final submission, demo page live |

---

## JUDGE SIMULATION PROCEDURE
Judges will:
1. Read SKILL.md cold (no prior knowledge)
2. Follow instructions to call `/api/v1/intents/register`
3. Retrieve the registered intent
4. Verify the cryptographic proof
5. Attempt to break the service (invalid inputs, missing fields)

**You pass if:** An AI agent with only your SKILL.md can complete all 3 tasks without human help.

---

## CRITICAL SUCCESS FACTORS

### DO:
- Keep SKILL.md under 200 lines but pack it with examples
- Include exact curl commands that work copy-paste
- Show sample JSON request AND response for every endpoint
- List every error code and what it means
- Provide a "Quick Start" section at the top

### DO NOT:
- Require API keys or authentication
- Use database that needs setup
- Have endpoints that return HTML instead of JSON
- Leave any field undocumented
- Use vague descriptions ("it processes the data")

---

## NANDA AGENT CARD TEMPLATE

```json
{
  "name": "AgentIntent Service",
  "version": "1.0.0",
  "description": "Cryptographic intent registration and verification for autonomous agents",
  "skill_url": "https://your-service.onrender.com/SKILL.md",
  "base_url": "https://your-service.onrender.com",
  "endpoints": [
    {
      "path": "/api/v1/intents/register",
      "method": "POST",
      "description": "Register a new agent intent"
    },
    {
      "path": "/api/v1/intents/{intent_id}",
      "method": "GET",
      "description": "Retrieve a registered intent"
    },
    {
      "path": "/api/v1/intents/{intent_id}/verify",
      "method": "GET",
      "description": "Verify cryptographic proof of intent"
    },
    {
      "path": "/api/v1/health",
      "method": "GET",
      "description": "Service health check"
    }
  ],
  "tags": ["intent", "verification", "NANDA", "agent"],
  "contact": "mavrriixx@gmail.com"
}
```

---

## RENDER DEPLOYMENT CHECKLIST
- [ ] `render.yaml` present in repo root
- [ ] `requirements.txt` with pinned versions
- [ ] `Procfile` or start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Environment: Python 3.11
- [ ] Free tier: 512MB RAM, sleeps after 15min inactivity (acceptable for demo)
- [ ] Custom domain not required, use `.onrender.com` subdomain
