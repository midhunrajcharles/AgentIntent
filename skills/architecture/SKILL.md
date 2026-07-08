# SKILL: AgentIntent System Architecture

## PURPOSE
Design and implement a clean, judge-ready AgentIntent service following the exact architecture rules for NandaHack.

---

## SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────┐
│              AgentIntent Service             │
│                                             │
│  ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │  FastAPI  │───▶│ Business │───▶│ Store │ │
│  │  Router   │    │  Logic   │    │ (dict)│ │
│  └──────────┘    └──────────┘    └───────┘ │
│       │                │                    │
│  ┌──────────┐    ┌──────────┐               │
│  │Middleware │    │  SHA256  │               │
│  │(rate lim) │    │ Hasher   │               │
│  └──────────┘    └──────────┘               │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Second Service  │  (composability demo)
│  (Verifier Bot)  │──▶ calls AgentIntent via HTTP
└─────────────────┘
```

---

## DATA MODELS (Pydantic v2)

### IntentRequest (POST body)
```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class IntentRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64, description="Unique agent identifier")
    action: str = Field(..., min_length=1, max_length=128, description="Intended action to perform")
    target: str = Field(..., description="Target resource or service URL")
    parameters: dict = Field(default_factory=dict, description="Action parameters as key-value pairs")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Intent lifetime in seconds")
    metadata: Optional[dict] = Field(default=None, description="Optional agent metadata")
```

### IntentRecord (stored + returned)
```python
import hashlib
import json
from datetime import datetime, timezone

class IntentRecord(BaseModel):
    intent_id: str                    # SHA256 of (agent_id + action + target + timestamp)
    agent_id: str
    action: str
    target: str
    parameters: dict
    status: Literal["pending", "active", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    proof_hash: str                   # SHA256 of full intent JSON
    metadata: Optional[dict] = None
```

### VerificationResult
```python
class VerificationResult(BaseModel):
    intent_id: str
    valid: bool
    status: str
    proof_hash: str
    computed_hash: str
    match: bool
    message: str
```

### ErrorResponse
```python
class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
```

---

## IN-MEMORY STORE DESIGN

```python
# Global store — survives process lifetime, resets on restart (acceptable for MVP)
from typing import Dict
from datetime import datetime, timezone

# Primary store
intents: Dict[str, IntentRecord] = {}

# Rate limiting store
rate_limits: Dict[str, list] = {}  # agent_id -> list of request timestamps

def get_intent(intent_id: str) -> IntentRecord | None:
    record = intents.get(intent_id)
    if record and record.expires_at < datetime.now(timezone.utc):
        record.status = "expired"
        intents[intent_id] = record
    return record

def store_intent(record: IntentRecord) -> None:
    intents[record.intent_id] = record

def list_intents(agent_id: str | None = None) -> list[IntentRecord]:
    all_records = list(intents.values())
    if agent_id:
        return [r for r in all_records if r.agent_id == agent_id]
    return all_records
```

---

## HASHING SCHEME

```python
import hashlib
import json
from datetime import datetime, timezone

def generate_intent_id(agent_id: str, action: str, target: str, timestamp: str) -> str:
    raw = f"{agent_id}:{action}:{target}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]  # short ID for readability

def generate_proof_hash(intent_data: dict) -> str:
    # Deterministic serialization — sort keys for consistency
    canonical = json.dumps(intent_data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()

def verify_proof(stored_record: IntentRecord) -> VerificationResult:
    data = {
        "intent_id": stored_record.intent_id,
        "agent_id": stored_record.agent_id,
        "action": stored_record.action,
        "target": stored_record.target,
        "parameters": stored_record.parameters,
        "created_at": stored_record.created_at.isoformat(),
    }
    computed = generate_proof_hash(data)
    match = computed == stored_record.proof_hash
    return VerificationResult(
        intent_id=stored_record.intent_id,
        valid=match and stored_record.status == "active",
        status=stored_record.status,
        proof_hash=stored_record.proof_hash,
        computed_hash=computed,
        match=match,
        message="Intent verified successfully" if match else "Proof hash mismatch — intent may be tampered"
    )
```

---

## INTENT STATE MACHINE

```
           ┌─────────┐
    POST   │         │
  ─────────▶  active │
           │         │
           └────┬────┘
                │
       ┌────────┼──────────┐
       │        │          │
  TTL expires  DELETE    admin
       │        │        revoke
       ▼        ▼          ▼
  ┌─────────┐ ┌────────┐ ┌─────────┐
  │ expired │ │deleted │ │ revoked │
  └─────────┘ └────────┘ └─────────┘
```

**Transitions:**
- `active` → `expired`: automatic when `expires_at < now()`
- `active` → `revoked`: via DELETE endpoint (soft delete, keeps record)
- Any state: readable via GET (shows current status)

---

## RATE LIMITING MIDDLEWARE

```python
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
import time

RATE_LIMIT = 60          # requests per window
RATE_WINDOW = 60         # seconds

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = RATE_LIMIT, period: int = RATE_WINDOW):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self._store: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next):
        # Use IP as key (X-Forwarded-For for Render proxy)
        client_ip = request.headers.get("X-Forwarded-For", request.client.host)
        now = time.time()

        if client_ip not in self._store:
            self._store[client_ip] = []

        # Prune old timestamps
        self._store[client_ip] = [t for t in self._store[client_ip] if now - t < self.period]

        if len(self._store[client_ip]) >= self.calls:
            return Response(
                content='{"error":"Rate limit exceeded","detail":"60 requests per minute allowed","status_code":429}',
                status_code=429,
                media_type="application/json"
            )

        self._store[client_ip].append(now)
        return await call_next(request)
```

---

## DIRECTORY STRUCTURE

```
agentintent/
├── main.py              # FastAPI app, middleware, startup
├── models.py            # All Pydantic models
├── store.py             # In-memory store operations
├── hashing.py           # SHA256 utilities
├── routers/
│   └── intents.py       # All intent endpoints
├── SKILL.md             # Agent-facing documentation (THE MOST IMPORTANT FILE)
├── requirements.txt
├── render.yaml
├── tests/
│   ├── test_intents.py
│   └── conftest.py
└── demo/
    └── index.html       # Single-file GitHub Pages demo
```

---

## SECOND SERVICE (COMPOSABILITY)

```
AgentVerifierBot/
├── main.py              # Calls AgentIntent via httpx
├── SKILL.md
└── requirements.txt
```

The second service exposes one endpoint:
- `POST /api/v1/verify-chain` — accepts `intent_id`, calls AgentIntent `/verify`, returns combined result

This proves composability: an agent using VerifierBot doesn't need to know about AgentIntent directly.
