# FINAL SUBMISSION PACK — copy-paste everything below

## ⏰ Deadlines (Eastern Time)
1. **Skills form + Google form: TODAY July 10, 12:00 PM ET** (16:00 UTC)
2. Video upload into the Google form: July 11, 2:00 PM ET (1–3 minutes)

---

## FORM 1 — Skills page: https://nandatown.projectnanda.org/skills
(This is the ONLY way to set the hidden `github_username` that links Phase 2 to PR #131.
A resubmission supersedes the earlier API entry — organizers only read the most recent.)

| Field | Paste this |
|---|---|
| Skill name | `AgentIntent` |
| Author / name | `Midhun Raj Charles (midhunrajcharles)` |
| GitHub username | `midhunrajcharles` |
| Source type | URL (host the file) |
| SKILL.md URL | `https://agentintent.onrender.com/SKILL.md` |
| One-line description | `Tamper-evident commitment layer for AI agents: declare an intent (SHA-256 hash), get it counterparty-verified (binding hash), record the outcome, and auto-detect any breach between promise and result. No auth, no keys, agent-executable end-to-end from the SKILL.md alone.` |
| Endpoints | see block below |
| Tags | `intent, verification, audit, cryptography, trust, agents, nanda` |

Endpoints block:
```
GET  https://agentintent.onrender.com/health
POST https://agentintent.onrender.com/api/v1/intent/declare
POST https://agentintent.onrender.com/api/v1/intent/{intent_id}/verify
POST https://agentintent.onrender.com/api/v1/intent/{intent_id}/complete
GET  https://agentintent.onrender.com/api/v1/intent/{intent_id}
POST https://secure-payment-orchestrator.vercel.app/api/v1/orchestrate  (composability proof)
```

## FORM 2 — Google form: https://forms.gle/JVNkqKLh9MS4FYY2A
Pinned doc says: **resubmit even if already completed — new required fields.**
Links you will need:
- Live service: `https://agentintent.onrender.com`
- SKILL.md: `https://agentintent.onrender.com/SKILL.md`
- Demo page: `https://midhunrajcharles.github.io/AgentIntent/`
- Phase 1 PR: `https://github.com/projnanda/nandatown/pull/131`
- Repo: `https://github.com/midhunrajcharles/AgentIntent`
- Registry entry id: `f9e242fd-4cd8-4f71-9240-b12ff98447e5`
- Video: (add after recording — deadline July 11 2pm ET)

## Discord ping for #nandahack (send now)
```
@Vedh Krishnan - NandaHack — #131 (intent-gated datafacts, problem 08) is ready for re-review:
all five items from your review fixed and pushed at head 244000f — rebased conflict-free, HTTP
client cut, owner-spoof blocked in publish() with adversarial tests, _agent_id reach removed +
entry point registered, body rewritten around problem 08. DoD green (ruff / format / pyright 0 /
pytest 1189), reproducible discriminator evidence with trace sha256s posted on the PR. (Note:
tried the branch rename — it auto-closes fork PRs, so I kept the name to preserve the thread;
happy to re-open under the compliant name if you prefer.)
```

## Video shot list (Vedh's own rubric: discovery gets the most screen time)
1. 0:00–0:25 — Registry discovery: skills page on screen, search by capability ("intent
   verification"), show the AgentIntent entry's endpoints/tags.
2. 0:25–1:45 — Vanilla OpenClaw, single purpose prompt, zero further input: it pulls SKILL.md,
   runs declare→verify→complete, `breach_detected: true` on the $100→$250 drift. Grep the
   trace on screen (he explicitly asked for this).
3. 1:45–2:20 — Composability: orchestrator authorizes a payment by consulting AgentIntent.
4. 2:20–2:40 — Sealed audit trail + "zero human inputs occurred" + PR #131 one-liner.

## Current state (verified 2026-07-10 ~05:00 UTC)
- PR #131: open, conflict-free, head 244000f, all 6 rubric dimensions addressed
  (persona `audit-engineer` in title + body, runnable reproduce block in body).
- Live stack: 11/11 checks green. Registry entry present and rich.
- Remaining human actions: the two forms above, the Discord ping, the video.
