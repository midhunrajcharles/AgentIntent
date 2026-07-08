#!/usr/bin/env bash
set -e

echo "=== AgentIntent Setup ==="

# Python version check
python3 --version | grep -E "3\.(11|12|13)" || {
  echo "ERROR: Python 3.11+ required"
  exit 1
}

# Create virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install agentintent deps
echo "Installing AgentIntent dependencies..."
pip install -r services/agentintent/requirements.txt -q

# Install orchestrator deps
echo "Installing Orchestrator dependencies..."
pip install -r services/secure-payment-orchestrator/requirements.txt -q

echo ""
echo "=== Setup complete ==="
echo ""
echo "Run AgentIntent:     cd services/agentintent && uvicorn main:app --reload --port 8000"
echo "Run Orchestrator:    cd services/secure-payment-orchestrator && uvicorn main:app --reload --port 8001"
echo "Run tests:           pytest tests/ -v --cov=services/agentintent --cov-report=term-missing"
echo "Open demo:           open demo/index.html"
