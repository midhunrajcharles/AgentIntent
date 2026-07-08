import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from models import IntentRecord, VerificationResult

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_intents: Dict[str, IntentRecord] = {}


def store_intent(record: IntentRecord) -> None:
    _intents[record.intent_id] = record


def get_intent(intent_id: str) -> Optional[IntentRecord]:
    record = _intents.get(intent_id)
    if record is None:
        return None
    if record.status == "active" and record.expires_at < datetime.now(timezone.utc):
        record = record.model_copy(update={"status": "expired"})
        _intents[intent_id] = record
    return record


def list_intents() -> list[IntentRecord]:
    return list(_intents.values())


def clear_store() -> None:
    _intents.clear()


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
def generate_intent_id(agent_id: str, action: str, target: str, timestamp: str) -> str:
    raw = f"{agent_id}:{action}:{target}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_proof_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_proof_data(intent_id: str, agent_id: str, action: str, target: str,
                     parameters: dict, created_at: datetime) -> dict:
    return {
        "intent_id": intent_id,
        "agent_id": agent_id,
        "action": action,
        "target": target,
        "parameters": parameters,
        "created_at": created_at.isoformat(),
    }


def verify_proof(record: IntentRecord) -> VerificationResult:
    data = build_proof_data(
        record.intent_id, record.agent_id, record.action,
        record.target, record.parameters, record.created_at,
    )
    computed = generate_proof_hash(data)
    match = computed == record.proof_hash
    valid = match and record.status == "active"
    if not match:
        message = "Proof hash mismatch — intent may be tampered"
    elif record.status != "active":
        message = f"Intent is {record.status}"
    else:
        message = "Intent verified successfully"
    return VerificationResult(
        intent_id=record.intent_id,
        valid=valid,
        status=record.status,
        proof_hash=record.proof_hash,
        computed_hash=computed,
        match=match,
        message=message,
    )
