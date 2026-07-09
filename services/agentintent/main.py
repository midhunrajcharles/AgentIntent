"""AgentIntent — Cryptographic intent registration and verification for autonomous agents."""
from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from models import IntentDeclarationRequest, OutcomeRecordRequest, VerificationRequest
from utils import (
    _compute_binding_hash,
    _compute_intent_hash,
    _detect_breach,
    _get_expiry,
    _is_expired,
    _now_iso,
)

# ---------------------------------------------------------------------------
# In-memory stores (module-level so tests can import and clear them)
# ---------------------------------------------------------------------------
intents_db: dict[str, dict] = {}
_rate_store: dict[str, list[float]] = {}


# ---------------------------------------------------------------------------
# Rate-limit middleware — 30 req / min per IP
# ---------------------------------------------------------------------------

#: Paths excluded from rate limiting: Render polls /health more often than the
#: per-IP budget allows, and discovery/docs pages must never 429 on a judge.
_RATE_EXEMPT_PATHS = {"/health", "/SKILL.md", "/docs", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 30, period: int = 60) -> None:
        super().__init__(app)
        self.calls = calls
        self.period = period

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _RATE_EXEMPT_PATHS:
            return await call_next(request)
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        now = time.time()
        window = _rate_store.setdefault(ip, [])
        _rate_store[ip] = [t for t in window if now - t < self.period]
        if len(_rate_store[ip]) >= self.calls:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"{self.calls} requests per minute allowed. Retry after 60s.",
                    "status_code": 429,
                },
            )
        _rate_store[ip].append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# App lifecycle — seed a persistent demo intent
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_demo()
    yield


def _seed_demo() -> None:
    """Insert a pre-built demo intent so judges can test without registering."""
    demo_id = "intent_demo000000"
    now = _now_iso()
    intents_db[demo_id] = {
        "intent_id": demo_id,
        "agent_id": "demo-agent",
        "intent_type": "demo_action",
        "details": {"target": "https://example.com", "demo": True},
        "max_cost": None,
        "timeout_seconds": 86400,
        "status": "pending",
        "created_at": now,
        "expires_at": _get_expiry(now, 86400),
        "intent_hash": _compute_intent_hash(
            "demo-agent", "demo_action", {"target": "https://example.com", "demo": True}
        ),
        "binding_hash": None,
        "verification": None,
        "outcome": None,
        "audit_trail": [
            {"event": "declared", "timestamp": now, "agent_id": "demo-agent", "note": "Pre-seeded demo intent"}
        ],
    }


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AgentIntent",
    description="Cryptographic intent registration, verification, and audit for autonomous agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RateLimitMiddleware, calls=30, period=60)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    # Pydantic v2 includes the raw Exception object inside ctx — strip it so
    # the dict is JSON-serializable regardless of the validator that fired.
    safe: list[dict] = []
    for err in exc.errors():
        clean: dict = {}
        for key, val in err.items():
            if key == "url":
                continue
            if key == "ctx" and isinstance(val, dict):
                clean[key] = {
                    ck: str(cv) if isinstance(cv, Exception) else cv
                    for ck, cv in val.items()
                }
            else:
                clean[key] = val
        safe.append(clean)
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": safe, "status_code": 422},
    )


@app.exception_handler(HTTPException)
async def _http_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        detail = {"error": detail, "detail": detail, "status_code": exc.status_code}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred.", "status_code": 500},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _fetch_or_404(intent_id: str) -> dict:
    """Return an intent record, auto-expiring it when TTL has elapsed."""
    record = intents_db.get(intent_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"No intent with ID '{intent_id}'", "status_code": 404},
        )
    if record["status"] not in ("expired", "completed", "rejected") and _is_expired(
        record["created_at"], record["timeout_seconds"]
    ):
        record["status"] = "expired"
        record["audit_trail"].append({"event": "expired", "timestamp": _now_iso()})
    return record


# ---------------------------------------------------------------------------
# Endpoint 0: Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health():
    """Liveness check. Cold-start on Render free tier takes up to 30s — retry if timeout."""
    return {
        "status": "healthy",
        "service": "AgentIntent",
        "version": "1.0.0",
        "timestamp": _now_iso(),
        "intents_stored": len(intents_db),
    }


# ---------------------------------------------------------------------------
# SKILL.md served as plain text (agent discovery)
# ---------------------------------------------------------------------------
@app.get("/SKILL.md", response_class=PlainTextResponse, include_in_schema=False)
def serve_skill_md():
    # Resolve relative to this module so the route works regardless of the
    # process working directory (pytest runs from the repo root).
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SKILL.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SKILL.md not found")


# ---------------------------------------------------------------------------
# Endpoint 1: POST /api/v1/intent/declare  →  201
# ---------------------------------------------------------------------------
@app.post("/api/v1/intent/declare", status_code=201, tags=["intent"])
def declare_intent(payload: IntentDeclarationRequest):
    """Register a new intent and receive a cryptographic hash commitment.

    State after call: ``pending``.
    Next step: POST ``/api/v1/intent/{intent_id}/verify``.
    """
    now = _now_iso()
    timeout = payload.timeout_seconds or 3600
    intent_id = f"intent_{uuid.uuid4().hex[:12]}"
    intent_hash = _compute_intent_hash(payload.agent_id, payload.intent_type, payload.details)
    expires_at = _get_expiry(now, timeout)

    intents_db[intent_id] = {
        "intent_id": intent_id,
        "agent_id": payload.agent_id,
        "intent_type": payload.intent_type,
        "details": payload.details,
        "max_cost": payload.max_cost,
        "timeout_seconds": timeout,
        "status": "pending",
        "created_at": now,
        "expires_at": expires_at,
        "intent_hash": intent_hash,
        "binding_hash": None,
        "verification": None,
        "outcome": None,
        "audit_trail": [
            {"event": "declared", "timestamp": now, "agent_id": payload.agent_id}
        ],
    }

    return {
        "intent_id": intent_id,
        "agent_id": payload.agent_id,
        "intent_type": payload.intent_type,
        "status": "pending",
        "intent_hash": intent_hash,
        "created_at": now,
        "expires_at": expires_at,
        "timeout_seconds": timeout,
        "max_cost": payload.max_cost,
        "message": "Intent declared. Submit to /verify before proceeding.",
    }


# ---------------------------------------------------------------------------
# Endpoint 2: POST /api/v1/intent/{intent_id}/verify  →  200
# ---------------------------------------------------------------------------
@app.post("/api/v1/intent/{intent_id}/verify", tags=["intent"])
def verify_intent(intent_id: str, payload: VerificationRequest):
    """Verify or reject a pending intent.

    - ``accepts=true``  → status becomes ``verified``; a binding hash is computed.
    - ``accepts=false`` → status becomes ``rejected``; no further transitions allowed.

    Returns 409 if the intent is not in ``pending`` state.
    Returns 400 if the intent has expired.
    """
    record = _fetch_or_404(intent_id)

    if record["status"] == "expired":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Intent expired",
                "detail": "This intent has expired. Declare a new intent.",
                "status_code": 400,
            },
        )
    if record["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Invalid state transition",
                "detail": (
                    f"Cannot verify an intent with status '{record['status']}'. "
                    "Only 'pending' intents can be verified."
                ),
                "status_code": 409,
            },
        )

    now = _now_iso()
    verification_record: dict = {
        "verifier_id": payload.verifier_id,
        "accepts": payload.accepts,
        "reason": payload.reason,
        "conditions": payload.conditions,
        "verified_at": now,
    }

    if payload.accepts:
        binding_hash = _compute_binding_hash(record, verification_record)
        record.update(
            status="verified",
            binding_hash=binding_hash,
            verification=verification_record,
        )
        record["audit_trail"].append({
            "event": "verified",
            "timestamp": now,
            "verifier_id": payload.verifier_id,
            "binding_hash": binding_hash,
        })
        message = "Intent verified. Binding commitment recorded. Proceed to /complete."
    else:
        record.update(status="rejected", verification=verification_record)
        record["audit_trail"].append({
            "event": "rejected",
            "timestamp": now,
            "verifier_id": payload.verifier_id,
            "reason": payload.reason,
        })
        message = "Intent rejected by verifier. Declare a new intent to retry."

    return {
        "intent_id": intent_id,
        "status": record["status"],
        "verified_by": payload.verifier_id,
        "accepted": payload.accepts,
        "binding_hash": record["binding_hash"],
        "reason": payload.reason,
        "verified_at": now,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Endpoint 3: POST /api/v1/intent/{intent_id}/complete  →  200
# ---------------------------------------------------------------------------
@app.post("/api/v1/intent/{intent_id}/complete", tags=["intent"])
def complete_intent(intent_id: str, payload: OutcomeRecordRequest):
    """Record the final outcome of a verified intent and run breach detection.

    - Intent must be in ``verified`` state (returns 400 otherwise).
    - Already-completed intents return 409.
    - Returns a full audit trail and breach report.
    """
    record = _fetch_or_404(intent_id)

    if record["status"] == "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Already completed",
                "detail": "This intent has already been completed.",
                "status_code": 409,
            },
        )
    if record["status"] != "verified":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Cannot complete intent",
                "detail": (
                    f"Intent must be in 'verified' state to complete. "
                    f"Current status: '{record['status']}'."
                ),
                "status_code": 400,
            },
        )

    now = _now_iso()
    actual = payload.actual_details or {}
    breach_report = _detect_breach(record["details"], actual)

    outcome_record: dict = {
        "reporter_id": payload.reporter_id,
        "outcome": payload.outcome,
        "evidence_hash": payload.evidence_hash,
        "actual_details": actual,
        "reported_at": now,
    }
    record.update(status="completed", outcome=outcome_record)
    record["audit_trail"].append({
        "event": "completed",
        "timestamp": now,
        "reporter_id": payload.reporter_id,
        "outcome": payload.outcome,
        "breach_detected": breach_report["breach_detected"],
        "severity": breach_report["severity"],
    })

    return {
        "intent_id": intent_id,
        "status": "completed",
        "outcome": payload.outcome,
        "reporter_id": payload.reporter_id,
        "completed_at": now,
        "breach_report": breach_report,
        "evidence_hash": payload.evidence_hash,
        "audit_trail": record["audit_trail"],
        "audit_ready": True,
        "message": (
            f"Intent completed with outcome '{payload.outcome}'. "
            f"Breach severity: {breach_report['severity']}."
        ),
    }


# ---------------------------------------------------------------------------
# Endpoint 4: GET /api/v1/intent/{intent_id}  →  200
# ---------------------------------------------------------------------------
@app.get("/api/v1/intent/{intent_id}", tags=["intent"])
def get_intent(intent_id: str):
    """Retrieve the current state and full metadata for an intent.

    Auto-transitions ``active`` → ``expired`` when TTL has elapsed.
    ``audit_ready`` is True once the intent is completed or both hashes exist.
    """
    record = _fetch_or_404(intent_id)
    audit_ready: bool = record["status"] == "completed" or (
        record["intent_hash"] is not None and record["binding_hash"] is not None
    )
    return {
        "intent_id": record["intent_id"],
        "agent_id": record["agent_id"],
        "intent_type": record["intent_type"],
        "details": record["details"],
        "max_cost": record["max_cost"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "intent_hash": record["intent_hash"],
        "binding_hash": record["binding_hash"],
        "verification": record["verification"],
        "outcome": record["outcome"],
        "audit_trail": record["audit_trail"],
        "audit_ready": audit_ready,
    }
