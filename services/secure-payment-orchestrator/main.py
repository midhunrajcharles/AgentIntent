"""Secure Payment Orchestrator — composability demo.

Verifies an AgentIntent intent exists and is in a valid state before
executing any payment action.  Calls the AgentIntent service over HTTP.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

AGENTINTENT_BASE = os.getenv("AGENTINTENT_BASE_URL", "https://agentintent.onrender.com")

# Statuses that indicate the intent is active (not yet acted upon)
_VALID_STATUSES = {"pending", "verified"}


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
    description="Composability demo: checks AgentIntent status before executing payment actions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": exc.errors(), "status_code": 422},
    )


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception):
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
    """Check the AgentIntent status for *intent_id* then mock-execute a payment.

    GET ``/api/v1/intent/{id}`` is called on the AgentIntent service.
    Statuses ``pending`` and ``verified`` are considered active; any other
    status (``rejected``, ``expired``, ``completed``) causes a rejection.
    """
    # --- Step 1: fetch intent from AgentIntent ---
    try:
        with httpx.Client(timeout=30.0) as client:
            intent_r = client.get(f"{AGENTINTENT_BASE}/api/v1/intent/{payload.intent_id}")
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "AgentIntent unreachable",
                "detail": f"Could not connect to {AGENTINTENT_BASE}",
                "status_code": 502,
            },
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "AgentIntent timeout",
                "detail": "Intent lookup timed out (cold start?). Retry in 15s.",
                "status_code": 504,
            },
        )

    if intent_r.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Intent not found",
                "detail": f"Intent '{payload.intent_id}' does not exist in AgentIntent.",
                "status_code": 404,
            },
        )
    if intent_r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "AgentIntent error",
                "detail": f"AgentIntent returned {intent_r.status_code}",
                "status_code": 502,
            },
        )

    intent = intent_r.json()
    intent_valid = intent.get("status") in _VALID_STATUSES

    # --- Step 2: mock-execute payment ---
    import hashlib, time as _time
    tx_id = hashlib.sha256(
        f"{payload.intent_id}:{payload.action}:{_time.time()}".encode()
    ).hexdigest()[:12]

    return OrchestrateResult(
        intent_id=payload.intent_id,
        action=payload.action,
        amount=payload.amount,
        recipient=payload.recipient,
        intent_verified=intent_valid,
        payment_status="authorized" if intent_valid else "rejected",
        transaction_id=tx_id if intent_valid else "NONE",
        timestamp=datetime.now(timezone.utc).isoformat(),
        message=(
            f"Payment authorized — intent status '{intent.get('status')}'"
            if intent_valid
            else f"Payment rejected — intent status '{intent.get('status')}'"
        ),
    )


@app.get("/SKILL_ORCH.md", response_class=PlainTextResponse, include_in_schema=False)
def serve_skill_md():
    # Resolve relative to this module so the route works regardless of the
    # process working directory (pytest runs from the repo root).
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SKILL_ORCH.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SKILL_ORCH.md not found")
