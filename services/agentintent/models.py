from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------
_AGENT_ID_RE = r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]*$"
_INTENT_TYPE_RE = r"^[a-z][a-z0-9_]*$"
_SHA256_RE = r"^[a-fA-F0-9]{64}$"
_VALID_URI_SCHEMES = ("https://", "http://", "nanda://", "df://")


# ---------------------------------------------------------------------------
# Rich declaration model — intent_type + details + optional cost/timeout
# ---------------------------------------------------------------------------

class IntentDeclarationRequest(BaseModel):
    """Richer intent declaration for scenarios that need cost caps and timeouts.

    Maps to the same registration endpoint but expresses intent as a typed
    declaration (intent_type + details dict) rather than an explicit
    action + target split.  Use ``target`` inside ``details`` to specify
    the resource URI; remaining keys become action parameters.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "agent_id": "buyer-agent-01",
                "intent_type": "purchase_token",
                "details": {
                    "target": "nanda://marketplace/tokens",
                    "token_id": "TOK-7821",
                    "quantity": 10,
                },
                "max_cost": 250.00,
                "timeout_seconds": 1800,
            }
        },
    )

    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=_AGENT_ID_RE,
        description="Unique agent identifier. Starts with alphanumeric; may contain hyphens, underscores, dots.",
        examples=["buyer-agent-01", "supplier-002"],
    )
    intent_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=_INTENT_TYPE_RE,
        description="Intent category in lower_snake_case (e.g. purchase_token, publish_dataset).",
        examples=["purchase_token", "publish_dataset", "authorize_payment"],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "All intent details as a flat or nested dict.  "
            "Include 'target' key for the resource URI; remaining keys become parameters."
        ),
        examples=[{"target": "nanda://marketplace/tokens", "token_id": "TOK-7821", "quantity": 10}],
    )
    max_cost: float | None = Field(
        default=None,
        gt=0,
        le=1_000_000,
        description="Optional cost ceiling in USD. The orchestrator will reject any action that exceeds this.",
        examples=[250.00, 1000.00],
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=60,
        le=86400,
        description="Optional intent lifetime override in seconds. Defaults to the service TTL (3600 s).",
        examples=[1800, 7200],
    )

    @field_validator("details")
    @classmethod
    def validate_details(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError(
                "details must not be empty — include at least one field (e.g. 'target')"
            )
        target = v.get("target")
        if target is not None:
            if not isinstance(target, str) or not any(
                str(target).startswith(s) for s in _VALID_URI_SCHEMES
            ):
                raise ValueError(
                    f"details.target must start with one of: {', '.join(_VALID_URI_SCHEMES)}"
                )
        return v


# ---------------------------------------------------------------------------
# Verification request — for agent-to-agent verification flows
# ---------------------------------------------------------------------------

class VerificationRequest(BaseModel):
    """Body for agent-to-agent verification flows (not required by the GET verify endpoint,
    but useful when a verifier agent wants to record its decision with context).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "verifier_id": "auditor-agent-01",
                "accepts": True,
                "reason": "Intent matches purchase order PO-4421",
                "conditions": ["amount <= 500", "vendor == 'ACME Corp'"],
            }
        },
    )

    verifier_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=_AGENT_ID_RE,
        description="ID of the agent performing verification.",
        examples=["auditor-agent-01", "risk-engine-v2"],
    )
    accepts: bool = Field(
        ...,
        description="Whether the verifier accepts the intent as valid.",
    )
    reason: str | None = Field(
        default=None,
        max_length=512,
        description="Human-readable reason for the accept/reject decision.",
        examples=["Intent matches purchase order PO-4421", "Amount exceeds threshold"],
    )
    conditions: list[str] | None = Field(
        default=None,
        description="Optional list of conditions that must hold for the verifier to accept.",
        examples=[["amount <= 500", "vendor == 'ACME Corp'"]],
    )

    @field_validator("conditions")
    @classmethod
    def conditions_max_length(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 20:
            raise ValueError("conditions list may not exceed 20 entries")
        return v


# ---------------------------------------------------------------------------
# Outcome record request — for closing the intent lifecycle
# ---------------------------------------------------------------------------

class OutcomeRecordRequest(BaseModel):
    """Body for recording the final outcome of an intent.

    The reporter agent calls this to close the intent lifecycle with an
    auditable outcome and optional evidence hash.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "reporter_id": "supplier-agent-01",
                "outcome": "fulfilled",
                "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "actual_details": {"units_delivered": 10, "invoice": "INV-4421"},
            }
        },
    )

    reporter_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=_AGENT_ID_RE,
        description="ID of the agent reporting the outcome.",
        examples=["supplier-agent-01", "settlement-engine"],
    )
    outcome: Literal["fulfilled", "cancelled", "failed", "disputed"] = Field(
        ...,
        description=(
            "Final outcome of the interaction. "
            "'fulfilled': completed as intended. "
            "'cancelled': aborted before completion. "
            "'failed': attempted but did not succeed. "
            "'disputed': outcome is contested by a party."
        ),
    )
    evidence_hash: str | None = Field(
        default=None,
        pattern=_SHA256_RE,
        description="SHA-256 hex digest of the evidence document (64-char lowercase hex). Optional.",
        examples=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )
    actual_details: dict[str, Any] | None = Field(
        default=None,
        description="Actual execution details — may differ from the original intent parameters.",
        examples=[{"units_delivered": 10, "invoice": "INV-4421"}],
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response from GET /health."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "AgentIntent",
                "version": "1.0.0",
                "timestamp": "2026-07-08T14:32:00.123456+00:00",
                "intents_stored": 1,
            }
        }
    )

    status: str
    service: str
    version: str
    timestamp: str
    intents_stored: int


# ---------------------------------------------------------------------------
# Standard envelope wrappers
# ---------------------------------------------------------------------------

class SuccessResponse(BaseModel):
    """Generic success envelope for endpoints that return varied payload shapes."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {"intent_id": "a3f7b2c1d4e5ab12"},
                "message": "Intent registered successfully",
            }
        }
    )

    success: bool = Field(default=True, description="Always True for this model.")
    data: dict[str, Any] = Field(..., description="Endpoint-specific payload.")
    message: str = Field(..., description="Human-readable summary.")


class ErrorResponse(BaseModel):
    """Standard error envelope returned on 4xx/5xx responses."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Intent not found",
                "detail": "No intent with ID 'xyz'",
                "status_code": 404,
            }
        }
    )

    success: bool = Field(default=False, description="Always False for this model.")
    error: str = Field(..., description="Short error category.")
    detail: str | list[Any] = Field(
        ...,
        description="Detailed error description. A list when multiple validation errors exist (422).",
    )
    status_code: int = Field(..., ge=400, le=599, description="HTTP status code.")
