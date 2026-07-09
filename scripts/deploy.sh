#!/usr/bin/env bash
set -e

echo "=== AgentIntent Deploy Checklist ==="

BASE_URL="${AGENTINTENT_URL:-https://agentintent.onrender.com}"
ORCH_URL="${ORCHESTRATOR_URL:-https://secure-payment-orchestrator.vercel.app}"

# 1. Run tests
echo "[1/5] Running tests..."
cd "$(dirname "$0")/.."
pytest tests/ -q --tb=short
echo "Tests passed."

# 2. Health check live service
echo "[2/5] Checking AgentIntent health at $BASE_URL..."
HEALTH=$(curl -s --max-time 35 "$BASE_URL/api/v1/health" || echo '{"status":"error"}')
STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))")
[ "$STATUS" = "healthy" ] || { echo "ERROR: AgentIntent not healthy. Deploy to Render first."; exit 1; }
echo "AgentIntent healthy."

# 3. Register test intent
echo "[3/5] Registering smoke-test intent..."
REGISTER=$(curl -s -X POST "$BASE_URL/api/v1/intents/register" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"deploy-check","action":"smoke_test","target":"https://example.com","parameters":{}}')
INTENT_ID=$(echo "$REGISTER" | python3 -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")
echo "Intent ID: $INTENT_ID"

# 4. Verify the intent
echo "[4/5] Verifying proof..."
VERIFY=$(curl -s "$BASE_URL/api/v1/intents/$INTENT_ID/verify")
VALID=$(echo "$VERIFY" | python3 -c "import sys,json; print(json.load(sys.stdin)['valid'])")
[ "$VALID" = "True" ] || { echo "ERROR: Verification failed: $VERIFY"; exit 1; }
echo "Proof verified."

# 5. Orchestrator health
echo "[5/5] Checking Orchestrator at $ORCH_URL..."
ORCH_HEALTH=$(curl -s --max-time 35 "$ORCH_URL/api/v1/health" || echo '{"status":"error"}')
ORCH_STATUS=$(echo "$ORCH_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))")
[ "$ORCH_STATUS" = "healthy" ] || echo "WARNING: Orchestrator not healthy (may need deploy)."

echo ""
echo "=== All checks passed ==="
echo "AgentIntent: $BASE_URL"
echo "SKILL.md:    $BASE_URL/SKILL.md"
echo "API Docs:    $BASE_URL/docs"
echo "Demo:        https://YOUR_GITHUB_USERNAME.github.io/Nandahack-Agentintent/"
