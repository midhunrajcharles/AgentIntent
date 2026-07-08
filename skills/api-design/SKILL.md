# SKILL: FastAPI Patterns & API Design for AgentIntent

## PURPOSE
Implement all AgentIntent endpoints following FastAPI best practices, with correct status codes, error handling, and response shapes that satisfy judge criteria.

---

## FULL main.py TEMPLATE

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from models import IntentRequest, IntentRecord, VerificationResult, ErrorResponse
from store import store_intent, get_intent, list_intents
from hashing import generate_intent_id, generate_proof_hash, verify_proof
from middleware import RateLimitMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed demo data so judges can test GET immediately
    seed_demo_intent()
    yield
    # Shutdown: nothing to clean up (in-memory)

app = FastAPI(
    title="AgentIntent Service",
    description="Cryptographic intent registration and verification for autonomous agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: open for demo/judges
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# Include routers
from routers.intents import router as intents_router
app.include_router(intents_router, prefix="/api/v1")

@app.get("/api/v1/health")
def health():
    return {
        "status": "healthy",
        "service": "AgentIntent",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intents_stored": len(list_intents()),
    }

@app.get("/SKILL.md", response_class=PlainTextResponse)
def serve_skill_md():
    with open("SKILL.md", "r") as f:
        return f.read()
```

---

## ENDPOINT SPECIFICATIONS

### POST /api/v1/intents/register

**Purpose:** Register a new agent intent with cryptographic proof

**Request:**
```json
{
  "agent_id": "agent-abc123",
  "action": "transfer_funds",
  "target": "https://payment.example.com/api/transfer",
  "parameters": {
    "amount": 100,
    "currency": "USD",
    "recipient": "user@example.com"
  },
  "ttl_seconds": 3600
}
```

**Response 201:**
```json
{
  "intent_id": "a3f7b2c1d4e5",
  "agent_id": "agent-abc123",
  "action": "transfer_funds",
  "target": "https://payment.example.com/api/transfer",
  "parameters": {"amount": 100, "currency": "USD", "recipient": "user@example.com"},
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T11:30:00Z",
  "proof_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb924...",
  "metadata": null
}
```

**Implementation:**
```python
@router.post("/intents/register", response_model=IntentRecord, status_code=201)
def register_intent(payload: IntentRequest):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=payload.ttl_seconds)
    
    intent_id = generate_intent_id(
        payload.agent_id, payload.action, payload.target, now.isoformat()
    )
    
    proof_data = {
        "intent_id": intent_id,
        "agent_id": payload.agent_id,
        "action": payload.action,
        "target": payload.target,
        "parameters": payload.parameters,
        "created_at": now.isoformat(),
    }
    proof_hash = generate_proof_hash(proof_data)
    
    record = IntentRecord(
        intent_id=intent_id,
        agent_id=payload.agent_id,
        action=payload.action,
        target=payload.target,
        parameters=payload.parameters,
        status="active",
        created_at=now,
        expires_at=expires,
        proof_hash=proof_hash,
        metadata=payload.metadata,
    )
    store_intent(record)
    return record
```

---

### GET /api/v1/intents/{intent_id}

**Purpose:** Retrieve a stored intent by ID

**Response 200:**
```json
{
  "intent_id": "a3f7b2c1d4e5",
  "agent_id": "agent-abc123",
  "action": "transfer_funds",
  "target": "https://payment.example.com/api/transfer",
  "parameters": {"amount": 100},
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T11:30:00Z",
  "proof_hash": "sha256:e3b0c44298fc1c..."
}
```

**Response 404:**
```json
{
  "error": "Intent not found",
  "detail": "No intent with ID 'xyz999' exists",
  "status_code": 404
}
```

**Implementation:**
```python
@router.get("/intents/{intent_id}", response_model=IntentRecord)
def get_intent_by_id(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": "Intent not found", "detail": f"No intent with ID '{intent_id}' exists", "status_code": 404}
        )
    return record
```

---

### GET /api/v1/intents/{intent_id}/verify

**Purpose:** Cryptographically verify an intent's proof hash

**Response 200 (valid):**
```json
{
  "intent_id": "a3f7b2c1d4e5",
  "valid": true,
  "status": "active",
  "proof_hash": "sha256:e3b0c44298fc1c...",
  "computed_hash": "sha256:e3b0c44298fc1c...",
  "match": true,
  "message": "Intent verified successfully"
}
```

**Response 200 (invalid — tampered):**
```json
{
  "intent_id": "a3f7b2c1d4e5",
  "valid": false,
  "status": "active",
  "proof_hash": "sha256:abc123...",
  "computed_hash": "sha256:def456...",
  "match": false,
  "message": "Proof hash mismatch — intent may be tampered"
}
```

**Implementation:**
```python
@router.get("/intents/{intent_id}/verify", response_model=VerificationResult)
def verify_intent(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Intent '{intent_id}' not found")
    return verify_proof(record)
```

---

### DELETE /api/v1/intents/{intent_id}

**Purpose:** Revoke an intent (soft delete — marks as revoked, keeps record)

**Response 200:**
```json
{
  "intent_id": "a3f7b2c1d4e5",
  "status": "revoked",
  "message": "Intent revoked successfully"
}
```

**Implementation:**
```python
@router.delete("/intents/{intent_id}")
def revoke_intent(intent_id: str):
    record = get_intent(intent_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Intent '{intent_id}' not found")
    record.status = "revoked"
    store_intent(record)
    return {"intent_id": intent_id, "status": "revoked", "message": "Intent revoked successfully"}
```

---

## HTTP STATUS CODE REFERENCE

| Code | When to use |
|------|------------|
| 200 | Successful GET, DELETE, verify |
| 201 | Successful POST (resource created) |
| 400 | Malformed JSON, validation error, missing required field |
| 404 | Intent ID not found |
| 422 | Pydantic validation error (auto-handled by FastAPI) |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |

---

## ERROR HANDLING PATTERN

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": exc.errors(),
            "status_code": 422,
        }
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
        content={"error": "Internal server error", "detail": str(exc), "status_code": 500}
    )
```

---

## REQUIREMENTS.TXT (pinned)

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.6
python-multipart==0.0.9
```

---

## RENDER.YAML

```yaml
services:
  - type: web
    name: agentintent
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    plan: free
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

---

## CURL TEST COMMANDS (copy-paste ready)

```bash
BASE=https://your-service.onrender.com

# Health check
curl $BASE/api/v1/health

# Register intent
curl -X POST $BASE/api/v1/intents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test-agent","action":"query_data","target":"https://api.example.com/data","parameters":{"limit":10}}'

# Get intent (replace INTENT_ID)
curl $BASE/api/v1/intents/INTENT_ID

# Verify intent
curl $BASE/api/v1/intents/INTENT_ID/verify

# Revoke intent
curl -X DELETE $BASE/api/v1/intents/INTENT_ID
```
