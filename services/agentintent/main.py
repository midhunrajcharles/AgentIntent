from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import time

from models import (
    IntentRequest, IntentRecord, VerificationResult,
    RevokeResult, HealthResponse,
)
from utils import (
    store_intent, get_intent, list_intents,
    generate_intent_id, generate_proof_hash,
    build_proof_data, verify_proof,
)

# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 60, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self._store: dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() \
                    or (request.client.host if request.client else "unknown")
        now = time.time()
        window = self._store.setdefault(client_ip, [])
        self._store[client_ip] = [t for t in window if now - t < self.period]
        if len(self._store[client_ip]) >= self.calls:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": "60 requests per minute allowed", "status_code": 429},
            )
        self._store[client_ip].append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed one demo intent so judges can GET immediately without registering first
    now = datetime.now(timezone.utc)
    demo_id = "demo0000000001"
    proof_data = build_proof_data(demo_id, "demo-agent", "demo_action",
                                  "https://example.com", {"demo": True}, now)
    record = IntentRecord(
        intent_id=demo_id,
        agent_id="demo-agent",
        action="demo_action",
        target="https://example.com",
        parameters={"demo": True},
        status="active",
        created_at=now,
        expires_at=now + timedelta(hours=24),
        proof_hash=generate_proof_hash(proof_data),
        metadata={"note": "Pre-seeded demo intent"},
    )
    store_intent(record)
    yield


app = FastAPI(
    title="AgentIntent Service",
    description="Cryptographic intent registration and verification for autonomous agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": exc.errors(), "status_code": 422},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        detail = {"error": detail, "detail": detail, "status_code": exc.status_code}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc), "status_code": 500},
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health():
    return HealthResponse(
        status="healthy",
        service="AgentIntent",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        intents_stored=len(list_intents()),
    )


# ---------------------------------------------------------------------------
# SKILL.md served as plain text (NANDA requirement)
# ---------------------------------------------------------------------------
@app.get("/SKILL.md", response_class=PlainTextResponse, include_in_schema=False)
def serve_skill_md():
    try:
        with open("SKILL.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SKILL.md not found")


# ---------------------------------------------------------------------------
# Intent endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/intents/register", response_model=IntentRecord, status_code=201, tags=["intents"])
def register_intent(payload: IntentRequest):
    now = datetime.now(timezone.utc)
    intent_id = generate_intent_id(payload.agent_id, payload.action, payload.target, now.isoformat())
    proof_data = build_proof_data(intent_id, payload.agent_id, payload.action,
                                  payload.target, payload.parameters, now)
    record = IntentRecord(
        intent_id=intent_id,
        agent_id=payload.agent_id,
        action=payload.action,
        target=payload.target,
        parameters=payload.parameters,
        status="active",
        created_at=now,
        expires_at=now + timedelta(seconds=payload.ttl_seconds),
        proof_hash=generate_proof_hash(proof_data),
        metadata=payload.metadata,
    )
    store_intent(record)
    return record


@app.get("/api/v1/intents/{intent_id}", response_model=IntentRecord, tags=["intents"])
def get_intent_by_id(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"No intent with ID '{intent_id}'", "status_code": 404},
        )
    return record


@app.get("/api/v1/intents/{intent_id}/verify", response_model=VerificationResult, tags=["intents"])
def verify_intent(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"No intent with ID '{intent_id}'", "status_code": 404},
        )
    return verify_proof(record)


@app.delete("/api/v1/intents/{intent_id}", response_model=RevokeResult, tags=["intents"])
def revoke_intent(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"No intent with ID '{intent_id}'", "status_code": 404},
        )
    updated = record.model_copy(update={"status": "revoked"})
    store_intent(updated)
    return RevokeResult(intent_id=intent_id, status="revoked", message="Intent revoked successfully")
