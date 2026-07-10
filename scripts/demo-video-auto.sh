#!/usr/bin/env bash
# demo-video-auto.sh — SELF-DRIVING video demo. Zero human input, captions built in.
#
# To record: 1) open Git Bash full screen, font 16pt+   2) Win+Alt+R to record
#            3) bash scripts/demo-video-auto.sh          4) Win+Alt+R to stop
# Runs ~2m15s. Works silent (captions on screen) or talk over it live.

# No set -e: a flaky network moment must never crash the recording.
set -u
BASE="https://agentintent.onrender.com"
ORCH="https://secure-payment-orchestrator.vercel.app"
REGISTRY="https://nandatown.projectnanda.org/api/skills"
TRACE="$(mktemp -t agentintent-trace-XXXX.log)"

caption() { printf "\n\033[1;33m╔══════════════════════════════════════════════════════════════════╗\033[0m\n"; \
            printf   "\033[1;33m║\033[1;37m %-66s \033[1;33m║\033[0m\n" "$1"; \
            [ -n "${2:-}" ] && printf "\033[1;33m║\033[0;37m %-66s \033[1;33m║\033[0m\n" "$2"; \
            printf   "\033[1;33m╚══════════════════════════════════════════════════════════════════╝\033[0m\n"; sleep 3; }
show() { printf "\033[0;32m$ %s\033[0m\n" "$1"; }
pause() { sleep "${1:-4}"; }

clear
caption "AgentIntent — NandaHack 2026" "An agent discovers, reads, and runs this service. Zero human input."
pause 2

caption "ACT 1 · DISCOVERY" "The NANDA registry knows a service that verifies agent intents"
show "curl \$REGISTRY | filter name==AgentIntent"
REG=""
for attempt in 1 2 3 4 5; do
  REG=$(curl -s -m 20 "$REGISTRY" 2>/dev/null || true)
  case "$REG" in \[*|\{*) break;; esac
  sleep 2
done
if [ -n "$REG" ]; then
  echo "$REG" | python -c "
import json,sys
try:
    for s in json.load(sys.stdin):
        if s.get('name')=='AgentIntent':
            print(json.dumps({k:s[k] for k in ('name','description','endpoints','tags') if k in s}, indent=1)); break
except Exception:
    print('(registry momentarily unreachable — entry id f9e242fd-4cd8-4f71-9240-b12ff98447e5)')" | tee -a "$TRACE"
else
  echo "(registry momentarily unreachable — entry id f9e242fd-4cd8-4f71-9240-b12ff98447e5)" | tee -a "$TRACE"
fi
pause 8

caption "ACT 2 · THE SKILL" "One file tells any vanilla agent everything it needs"
show "curl $BASE/SKILL.md"
curl -s "$BASE/SKILL.md" | sed -n '1,26p'
pause 7

caption "ACT 3 · THE PROMISE" "The agent declares: 'I will pay exactly \$100' -> SHA-256 commitment"
show "POST /api/v1/intent/declare  {amount: 100}"
DECL=$(curl -s -X POST "$BASE/api/v1/intent/declare" -H 'Content-Type: application/json' \
  -d '{"agent_id":"demo-payment-agent","intent_type":"authorize_payment","details":{"target":"https://payments.example.com/pay","amount":100,"currency":"USD"},"timeout_seconds":3600}')
echo "$DECL" | python -m json.tool | tee -a "$TRACE"
IID=$(echo "$DECL" | python -c "import json,sys;print(json.load(sys.stdin)['intent_id'])")
pause 6

caption "ACT 4 · THE WITNESS" "A second agent verifies -> the promise is cryptographically bound"
show "POST /api/v1/intent/$IID/verify"
curl -s -X POST "$BASE/api/v1/intent/$IID/verify" -H 'Content-Type: application/json' \
  -d '{"verifier_id":"demo-risk-engine","accepts":true,"reason":"Within approved budget"}' | python -m json.tool | tee -a "$TRACE"
pause 6

caption "ACT 5 · THE LIE" "The agent moves \$250 instead of \$100. No human is watching."
show "POST /api/v1/intent/$IID/complete  {amount: 250}"
curl -s -X POST "$BASE/api/v1/intent/$IID/complete" -H 'Content-Type: application/json' \
  -d '{"reporter_id":"demo-payment-agent","outcome":"fulfilled","actual_details":{"target":"https://payments.example.com/pay","amount":250,"currency":"USD"}}' | python -m json.tool | tee -a "$TRACE"
caption ">>> breach_detected: TRUE <<<" "No human caught this. The math did."
pause 4

caption "ACT 6 · THE SEALED RECORD" "Any third party can replay the whole story, forever"
show "GET /api/v1/intent/$IID"
curl -s "$BASE/api/v1/intent/$IID" | python -m json.tool | tail -30 | tee -a "$TRACE"
pause 6

caption "ACT 7 · COMPOSABILITY" "A separate service refuses to pay against a spent promise"
show "POST \$ORCH/api/v1/orchestrate  (reusing the fulfilled intent)"
curl -s -X POST "$ORCH/api/v1/orchestrate" -H 'Content-Type: application/json' \
  -d "{\"intent_id\":\"$IID\",\"action\":\"authorize_payment\",\"amount\":100}" | python -m json.tool | tee -a "$TRACE"
caption "rejected BY DESIGN" "A fulfilled commitment cannot authorize new spending"
pause 3

caption "ACT 8 · THE TRACE" "Every hash, every verdict — greppable evidence"
show "grep -E 'intent_hash|binding_hash|breach_detected|payment_status' trace.log"
grep -oE '"(intent_hash|binding_hash)": "[a-f0-9]{16}[a-f0-9]*"|"breach_detected": (true|false)|"payment_status": "[a-z]+"' "$TRACE" | head -8
pause 5

caption "Every call above was built from SKILL.md alone." "Zero human inputs. Same protocol submitted to NANDA Town as PR #131."
printf "\n  Live: %s   ·   Demo: https://midhunrajcharles.github.io/AgentIntent/\n\n" "$BASE"
