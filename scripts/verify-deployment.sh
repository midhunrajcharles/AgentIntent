#!/bin/bash
# ══════════════════════════════════════════════════════
#  FINAL DEPLOYMENT VERIFICATION SCRIPT
#  Run AFTER both services are live:
#    bash scripts/verify-deployment.sh [agentintent-url] [orchestrator-url]
# ══════════════════════════════════════════════════════

AGENTINTENT_URL="${1:-https://agentintent.onrender.com}"
ORCHESTRATOR_URL="${2:-https://secure-payment-orchestrator.vercel.app}"

echo "🚀 NandaHack Final Verification"
echo "  AgentIntent:  $AGENTINTENT_URL"
echo "  Orchestrator: $ORCHESTRATOR_URL"
echo "================================"

PASS=0
FAIL=0

check() {
  local description="$1"
  local command="$2"
  echo -n "Testing: $description ... "
  if eval "$command" > /dev/null 2>&1; then
    echo "✅ PASS"
    PASS=$((PASS + 1))
  else
    echo "❌ FAIL"
    FAIL=$((FAIL + 1))
  fi
}

# Find a real Python (Windows ships a fake python3 stub that exits 49)
PY=""
for cand in python3 python py; do
  if "$cand" -c "import json" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then echo "❌ No working Python found on PATH"; exit 1; fi

json_field() {  # json_field '<json>' <key>
  "$PY" -c "import sys, json; print(json.loads(sys.argv[1])[sys.argv[2]])" "$1" "$2" 2>/dev/null
}

# ===== SERVICE 1: HEALTH (exempt from rate limiting) =====
check "AgentIntent /health returns healthy" \
  "curl -m 30 -sf ${AGENTINTENT_URL}/health | grep -q '\"healthy\"'"

# ===== SERVICE 1: SKILL.MD SERVING =====
check "SKILL.md accessible via HTTP" \
  "curl -m 30 -sf ${AGENTINTENT_URL}/SKILL.md | grep -q 'AgentIntent'"

# ===== SERVICE 1: DECLARE =====
DECLARE_RESULT=$(curl -m 30 -sf -X POST "${AGENTINTENT_URL}/api/v1/intent/declare" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"judge-test-001","intent_type":"authorize_payment","details":{"target":"https://payment.example.com/pay","amount":100,"currency":"USD"},"timeout_seconds":3600}')

check "Declare returns intent_id + intent_hash" \
  "echo '$DECLARE_RESULT' | grep -q intent_id && echo '$DECLARE_RESULT' | grep -q intent_hash"

INTENT_ID=$(json_field "$DECLARE_RESULT" intent_id)

# ===== SERVICE 1: VERIFY =====
VERIFY_RESULT=$(curl -m 30 -sf -X POST "${AGENTINTENT_URL}/api/v1/intent/${INTENT_ID}/verify" \
  -H "Content-Type: application/json" \
  -d '{"verifier_id":"judge-counterparty","accepts":true,"reason":"smoke test"}')

check "Verify produces binding_hash" \
  "echo '$VERIFY_RESULT' | grep -q binding_hash"

# ===== SERVICE 1: COMPLETE (valid outcomes: fulfilled/cancelled/failed/disputed) =====
COMPLETE_RESULT=$(curl -m 30 -sf -X POST "${AGENTINTENT_URL}/api/v1/intent/${INTENT_ID}/complete" \
  -H "Content-Type: application/json" \
  -d '{"reporter_id":"judge-test-001","outcome":"fulfilled","actual_details":{"target":"https://payment.example.com/pay","amount":100,"currency":"USD"}}')

check "Complete includes audit_trail + breach_report" \
  "echo '$COMPLETE_RESULT' | grep -q audit_trail && echo '$COMPLETE_RESULT' | grep -q breach_report"

# ===== SERVICE 1: AUDIT + ERRORS =====
check "GET intent returns full audit record" \
  "curl -m 30 -sf ${AGENTINTENT_URL}/api/v1/intent/${INTENT_ID} | grep -q audit_trail"

check "404 for invalid intent ID" \
  "test \"\$(curl -m 30 -s -o /dev/null -w '%{http_code}' ${AGENTINTENT_URL}/api/v1/intent/fake_id_12345)\" = 404"

check "Seed demo intent always available" \
  "curl -m 30 -sf ${AGENTINTENT_URL}/api/v1/intent/intent_demo000000 | grep -q intent_demo000000"

# ===== SERVICE 2: HEALTH =====
check "Orchestrator /api/v1/health returns healthy" \
  "curl -m 30 -sf ${ORCHESTRATOR_URL}/api/v1/health | grep -q '\"healthy\"'"

# ===== SERVICE 2: COMPOSITION (declare fresh intent, then orchestrate) =====
COMPOSE_INTENT=$(curl -m 30 -sf -X POST "${AGENTINTENT_URL}/api/v1/intent/declare" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"orch-smoke","intent_type":"authorize_payment","details":{"target":"https://payment.example.com/pay","amount":75}}')
COMPOSE_ID=$(json_field "$COMPOSE_INTENT" intent_id)

COMPOSE_RESULT=$(curl -m 30 -sf -X POST "${ORCHESTRATOR_URL}/api/v1/orchestrate" \
  -H "Content-Type: application/json" \
  -d "{\"intent_id\":\"${COMPOSE_ID}\",\"action\":\"authorize_payment\",\"amount\":75.00}")

check "Orchestrator authorizes payment via AgentIntent (composition proof)" \
  "echo '$COMPOSE_RESULT' | grep -q '\"authorized\"' && echo '$COMPOSE_RESULT' | grep -q ${COMPOSE_ID}"

check "Orchestrator 404s for unknown intent" \
  "test \"\$(curl -m 30 -s -o /dev/null -w '%{http_code}' -X POST ${ORCHESTRATOR_URL}/api/v1/orchestrate -H 'Content-Type: application/json' -d '{\"intent_id\":\"fake\",\"action\":\"authorize_payment\",\"amount\":10}')\" = 404"

# ===== SUMMARY =====
echo ""
echo "================================"
echo "Results: ${PASS} passed, ${FAIL} failed"
echo ""

if [ $FAIL -eq 0 ]; then
  echo "🎉 ALL TESTS PASSED! READY TO SUBMIT!"
  echo ""
  echo "Live URLs:"
  echo "  Service 1: ${AGENTINTENT_URL}"
  echo "  Service 2: ${ORCHESTRATOR_URL}"
  exit 0
else
  echo "⚠️  ${FAIL} test(s) failed. FIX BEFORE SUBMITTING!"
  echo "(Cold start on Render free tier takes ~30s — if failures look like timeouts, rerun once.)"
  exit 1
fi
