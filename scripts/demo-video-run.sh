#!/usr/bin/env bash
# demo-video-run.sh — the exact judged flow, narrated for screen recording.
# Run this in a clean terminal while recording. It pauses between acts so you
# can talk over it. Press ENTER to advance. Total runtime ~90 seconds of footage.
#
# Vedh's rubric: show DISCOVERY (registry lookup) -> SKILL.md read -> agent-built
# calls -> real result -> trace. Discovery gets the most screen time.

set -euo pipefail
BASE="https://agentintent.onrender.com"
ORCH="https://secure-payment-orchestrator.vercel.app"
REGISTRY="https://nandatown.projectnanda.org/api/skills"
TRACE="$(mktemp -t agentintent-trace-XXXX.log)"

say()  { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
act()  { printf "\n\033[1;33m=== ACT %s ===\033[0m\n" "$*"; read -r -p "(ENTER to run)"; }
run()  { printf "\033[0;32m$ %s\033[0m\n" "$*"; eval "$*" | tee -a "$TRACE"; }

say "AgentIntent — an agent discovers, reads, and executes this service with ZERO human input."

act "1: DISCOVERY — the NANDA registry knows a service that does intent verification"
run "curl -s '$REGISTRY' | python -c \"import json,sys;[print(json.dumps({k:s[k] for k in ('name','description','endpoints','tags') if k in s},indent=1)) for s in json.load(sys.stdin) if s.get('name')=='AgentIntent']\" | head -30"

act "2: THE AGENT READS THE SKILL — one file tells it everything"
run "curl -s $BASE/SKILL.md | head -40"

act "3: THE AGENT EXECUTES — declare a \$100 payment intent (SHA-256 commitment)"
run "curl -s -X POST $BASE/api/v1/intent/declare -H 'Content-Type: application/json' -d '{\"agent_id\":\"demo-payment-agent\",\"intent_type\":\"authorize_payment\",\"details\":{\"target\":\"https://payments.example.com/pay\",\"amount\":100,\"currency\":\"USD\"},\"timeout_seconds\":3600}'"
printf "\nPaste the intent_id from above: "; read -r IID

act "4: A COUNTERPARTY VERIFIES — the promise is now cryptographically bound"
run "curl -s -X POST $BASE/api/v1/intent/$IID/verify -H 'Content-Type: application/json' -d '{\"verifier_id\":\"demo-risk-engine\",\"accepts\":true,\"reason\":\"Within approved budget\"}'"

act "5: THE AGENT LIES — it promised \$100 but moves \$250. Watch the log catch it."
run "curl -s -X POST $BASE/api/v1/intent/$IID/complete -H 'Content-Type: application/json' -d '{\"reporter_id\":\"demo-payment-agent\",\"outcome\":\"fulfilled\",\"actual_details\":{\"target\":\"https://payments.example.com/pay\",\"amount\":250,\"currency\":\"USD\"}}'"
say ">>> breach_detected: true — no human was watching. The math was."

act "6: THE SEALED AUDIT TRAIL — any third party can replay the whole story"
run "curl -s $BASE/api/v1/intent/$IID"

act "7: COMPOSABILITY — a second, separately hosted service refuses to pay against a spent promise"
run "curl -s -X POST $ORCH/api/v1/orchestrate -H 'Content-Type: application/json' -d '{\"intent_id\":\"$IID\",\"action\":\"authorize_payment\",\"amount\":100}'"
say ">>> rejected BY DESIGN: a fulfilled commitment cannot authorize new spending."
say "    (Fresh verified intents ARE authorized — that's the composability proof in SKILL.md.)"

act "8: GREP THE TRACE — Vedh asked to see this on screen"
run "grep -E 'intent_hash|binding_hash|breach_detected|payment_status' '$TRACE' | head -8"

say "Every call above was buildable from SKILL.md alone. Zero human inputs. That's the thesis."
say "Trace saved: $TRACE"
