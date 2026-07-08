from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class IntentRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    action: str = Field(..., min_length=1, max_length=128)
    target: str = Field(..., min_length=1)
    parameters: dict = Field(default_factory=dict)
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    metadata: Optional[dict] = None


class IntentRecord(BaseModel):
    intent_id: str
    agent_id: str
    action: str
    target: str
    parameters: dict
    status: Literal["active", "expired", "revoked"]
    created_at: datetime
    expires_at: datetime
    proof_hash: str
    metadata: Optional[dict] = None


class VerificationResult(BaseModel):
    intent_id: str
    valid: bool
    status: str
    proof_hash: str
    computed_hash: str
    match: bool
    message: str


class RevokeResult(BaseModel):
    intent_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    intents_stored: int
