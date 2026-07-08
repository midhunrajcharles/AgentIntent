"""
Secure Payment Orchestrator — second service demonstrating composability.
Verifies an AgentIntent proof before executing any payment action.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

AGENTINTENT_BASE = os.getenv("AGENTINTENT_BASE_URL", "https://agentintent.onrender.com")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class OrchestrateRequest(BaseModel):
    intent_id: str = Field(..., min_length=1, description="Intent ID from AgentIntent service")
    action: str = Field(..., description="Payment action to perform")
    amount: float = Field(..., gt=0, le=10000, description="Amount in USD (max $10,000)")
    recipient: str = Field(default="mock-recipient@example.com")


class OrchestrateResult(BaseModel):
    intent_id: str
    action: str
    amount: float
    recipient: str
    intent_verified: bool
    payment_status: str
    transaction_id: str
    timestamp: str
    message: str


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Secure Payment Orchestrator",
    description="Composability demo: verifies AgentIntent proof before executing payment actions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc), "status_code": 500},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
def health():
    return {
        "status": "healthy",
        "service": "SecurePaymentOrchestrator",
        "version": "1.0.0",
        "agentintent_base": AGENTINTENT_BASE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/orchestrate", response_model=OrchestrateResult, status_code=200)
def orchestrate(payload: OrchestrateRequest):
    # Step 1: verify intent with AgentIntent service
    try:
        with httpx.Client(timeout=30.0) as client:
            verify_r = client.get(f"{AGENTINTENT_BASE}/api/v1/intents/{payload.intent_id}/verify")
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail={"error": "AgentIntent unreachable", "detail": f"Could not connect to {AGENTINTENT_BASE}", "status_code": 502},
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={"error": "AgentIntent timeout", "detail": "Verification request timed out (cold start?). Retry in 15s.", "status_code": 504},
        )

    if verify_r.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"Intent '{payload.intent_id}' does not exist in AgentIntent", "status_code": 404},
        )

    if verify_r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={"error": "Verification failed", "detail": f"AgentIntent returned {verify_r.status_code}", "status_code": 502},
        )

    verification = verify_r.json()
    intent_valid = verification.get("valid", False) and verification.get("match", False)

    # Step 2: mock payment execution (no real payment processed)
    import hashlib, time
    tx_id = hashlib.sha256(f"{payload.intent_id}:{payload.action}:{time.time()}".encode()).hexdigest()[:12]

    return OrchestrateResult(
        intent_id=payload.intent_id,
        action=payload.action,
        amount=payload.amount,
        recipient=payload.recipient,
        intent_verified=intent_valid,
        payment_status="authorized" if intent_valid else "rejected",
        transaction_id=tx_id if intent_valid else "NONE",
        timestamp=datetime.now(timezone.utc).isoformat(),
        message="Payment authorized via verified intent" if intent_valid
                else "Payment rejected: intent verification failed",
    )


@app.get("/SKILL_ORCH.md", response_class=PlainTextResponse, include_in_schema=False)
def serve_skill_md():
    try:
        with open("SKILL_ORCH.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SKILL_ORCH.md not found")
