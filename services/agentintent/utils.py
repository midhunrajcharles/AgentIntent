from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time utilities
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Returns:
        str: Current UTC timestamp, e.g. ``"2026-07-08T14:32:00.123456+00:00"``.
             Falls back to the Unix epoch string if the system clock fails.

    Example:
        >>> ts = _now_iso()
        >>> ts.endswith("+00:00")
        True
    """
    try:
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        logger.exception("_now_iso: clock read failed; returning epoch fallback")
        return "1970-01-01T00:00:00.000000+00:00"


def _get_expiry(timestamp: str | datetime, timeout_seconds: int) -> str:
    """Calculate an expiry timestamp by adding *timeout_seconds* to *timestamp*.

    Args:
        timestamp: Base time as a tz-aware ``datetime`` or an ISO 8601 string.
            Naive datetimes are assumed to be UTC.
        timeout_seconds: Number of seconds to add. Must be non-negative.

    Returns:
        str: Expiry timestamp in ISO 8601 format.
             Returns ``"2099-12-31T23:59:59+00:00"`` (far future) if parsing
             or arithmetic fails, so callers always get a usable string.

    Example:
        >>> _get_expiry("2026-07-08T00:00:00+00:00", 3600)
        '2026-07-08T01:00:00+00:00'
    """
    _FALLBACK = "2099-12-31T23:59:59+00:00"
    try:
        if isinstance(timestamp, str):
            base: datetime = datetime.fromisoformat(timestamp)
        else:
            base = timestamp
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return (base + timedelta(seconds=timeout_seconds)).isoformat()
    except Exception:
        logger.exception(
            "_get_expiry: failed for timestamp=%r timeout=%r; returning far-future fallback",
            timestamp,
            timeout_seconds,
        )
        return _FALLBACK


def _is_expired(timestamp: str | datetime, timeout_seconds: int) -> bool:
    """Check whether *timestamp* + *timeout_seconds* is in the past.

    Fail-safe: returns ``True`` (treats the record as expired) if parsing fails,
    because permitting an unverifiable record to appear valid is a worse failure
    mode than incorrectly expiring it.

    Args:
        timestamp: Start time as a tz-aware ``datetime`` or an ISO 8601 string.
            Naive datetimes are assumed to be UTC.
        timeout_seconds: Lifetime in seconds.

    Returns:
        bool: ``True`` if the computed expiry is strictly before now, ``False``
              otherwise. Also returns ``True`` on any exception.

    Example:
        >>> _is_expired("1970-01-01T00:00:00+00:00", 60)
        True
    """
    try:
        if isinstance(timestamp, str):
            base: datetime = datetime.fromisoformat(timestamp)
        else:
            base = timestamp
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        expiry = base + timedelta(seconds=timeout_seconds)
        return expiry < datetime.now(timezone.utc)
    except Exception:
        logger.exception(
            "_is_expired: failed for timestamp=%r timeout=%r; treating as expired",
            timestamp,
            timeout_seconds,
        )
        return True  # fail-safe


# ---------------------------------------------------------------------------
# Hash utilities
# ---------------------------------------------------------------------------

def _compute_hash(data_dict: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of a JSON-serializable dict.

    Serialises *data_dict* to compact JSON with lexicographically sorted keys
    (``sort_keys=True``, no extra whitespace) so that the same logical content
    always produces the same digest regardless of insertion order.

    Args:
        data_dict: Any dict whose values are JSON-serialisable.  Non-serialisable
            values (e.g. ``datetime``) are coerced to strings via ``default=str``.

    Returns:
        str: 64-character lowercase hex SHA-256 digest.
             Returns ``"0" * 64`` (a sentinel) if serialisation fails, so callers
             always receive a string of the expected length.

    Example:
        >>> _compute_hash({"b": 2, "a": 1}) == _compute_hash({"a": 1, "b": 2})
        True
    """
    try:
        canonical = json.dumps(
            data_dict,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("_compute_hash: serialisation failed for keys=%r", list(data_dict))
        return "0" * 64


def _compute_intent_hash(
    agent_id: str,
    intent_type: str,
    details: dict[str, Any],
) -> str:
    """Compute a canonical fingerprint for a declared intent.

    Combines *agent_id*, *intent_type*, and *details* into a single structure
    before hashing.  This hash uniquely identifies the intent as declared at
    registration time and can be used to detect tampering with any of the
    three core fields.

    Args:
        agent_id: Unique identifier of the declaring agent.
        intent_type: Action category, e.g. ``"purchase_token"`` or ``"publish_dataset"``.
        details: Arbitrary intent detail dict.  May include a ``"target"`` key and
            any number of action parameters.

    Returns:
        str: 64-character lowercase hex SHA-256 digest, or ``"0" * 64`` on error.

    Example:
        >>> h1 = _compute_intent_hash("agent-1", "buy", {"amount": 10})
        >>> h2 = _compute_intent_hash("agent-1", "buy", {"amount": 10})
        >>> h1 == h2
        True
    """
    payload: dict[str, Any] = {
        "agent_id": agent_id,
        "intent_type": intent_type,
        "details": details,
    }
    return _compute_hash(payload)


def _compute_binding_hash(
    intent: dict[str, Any],
    verification: dict[str, Any],
) -> str:
    """Compute a commitment hash binding an intent record to a verification decision.

    Produces a tamper-evident link: if either the intent data or the verifier's
    decision changes after this hash is recorded, the hash will no longer match.
    Suitable for audit trails and multi-party accountability.

    Args:
        intent: The full intent record as a plain dict.  All fields are
            included in the hash.
        verification: The verifier's decision dict, e.g.
            ``{"verifier_id": "...", "accepts": True, "reason": "..."}``.

    Returns:
        str: 64-character lowercase hex SHA-256 digest binding both inputs,
             or ``"0" * 64`` on error.

    Example:
        >>> intent = {"intent_id": "abc", "agent_id": "a1", "action": "buy"}
        >>> verif  = {"verifier_id": "v1", "accepts": True}
        >>> len(_compute_binding_hash(intent, verif))
        64
    """
    payload: dict[str, Any] = {
        "intent": intent,
        "verification": verification,
    }
    return _compute_hash(payload)


# ---------------------------------------------------------------------------
# Breach detection
# ---------------------------------------------------------------------------

#: Relative tolerance for numeric field comparisons in breach detection.
_NUMERIC_TOLERANCE: float = 0.05  # 5 %


def _detect_breach(
    intent_details: dict[str, Any],
    outcome_details: dict[str, Any],
) -> dict[str, Any]:
    """Detect breaches by comparing declared intent details against recorded outcome.

    A *breach* is any field in *intent_details* whose corresponding value in
    *outcome_details* differs materially:

    * **Omission** — the field is absent from *outcome_details*.
    * **Numeric deviation** — the relative difference exceeds 5 %.
    * **String mismatch** — case-sensitive inequality.
    * **Type mismatch** — the Python types differ.
    * **Generic mismatch** — equality check fails for booleans, lists, dicts, etc.

    Extra keys in *outcome_details* that are not in *intent_details* are ignored
    (outcomes may legally contain more information than the original declaration).

    This function **never raises**.  If an unexpected error occurs during
    comparison, the result is returned with ``breach_detected=False`` and a
    ``_error`` key explaining that a manual audit is required.

    Args:
        intent_details: The ``parameters`` / ``details`` dict from the original
            intent registration (what was *declared*).
        outcome_details: The ``actual_details`` dict from the outcome record
            (what *actually happened*).

    Returns:
        dict: A result dict with the following keys:

            - ``"breach_detected"`` (bool): ``True`` if at least one breach was found.
            - ``"breaches"`` (list[dict]): Each entry contains:
                ``"field"`` (str), ``"expected"`` (Any), ``"actual"`` (Any),
                ``"reason"`` (str).
            - ``"breach_count"`` (int): Total number of distinct breaches.
            - ``"severity"`` (str): ``"none"``, ``"minor"`` (1–2 breaches), or
                ``"major"`` (3 or more breaches).

    Example:
        >>> result = _detect_breach(
        ...     {"amount": 100, "currency": "USD"},
        ...     {"amount": 200, "currency": "USD"},
        ... )
        >>> result["breach_detected"]
        True
        >>> result["breaches"][0]["field"]
        'amount'
        >>> result["severity"]
        'minor'
    """
    breaches: list[dict[str, Any]] = []

    try:
        for key, expected in intent_details.items():
            if key not in outcome_details:
                breaches.append({
                    "field": key,
                    "expected": expected,
                    "actual": None,
                    "reason": "field omitted from outcome",
                })
                continue

            actual = outcome_details[key]

            # --- Bool: handle before int/float (bool is a subclass of int in Python) ---
            if isinstance(expected, bool) or isinstance(actual, bool):
                if type(expected) is not type(actual):
                    breaches.append({
                        "field": key,
                        "expected": expected,
                        "actual": actual,
                        "reason": (
                            f"type mismatch: declared {type(expected).__name__}, "
                            f"received {type(actual).__name__}"
                        ),
                    })
                elif expected != actual:
                    breaches.append({
                        "field": key,
                        "expected": expected,
                        "actual": actual,
                        "reason": "boolean value mismatch",
                    })

            # --- Numeric: compare with relative tolerance ---
            elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                if expected != 0:
                    relative_diff = abs(actual - expected) / abs(expected)
                    if relative_diff > _NUMERIC_TOLERANCE:
                        breaches.append({
                            "field": key,
                            "expected": expected,
                            "actual": actual,
                            "reason": (
                                f"numeric deviation {relative_diff:.1%} exceeds "
                                f"{_NUMERIC_TOLERANCE:.0%} tolerance"
                            ),
                        })
                elif actual != 0:
                    breaches.append({
                        "field": key,
                        "expected": expected,
                        "actual": actual,
                        "reason": "expected zero but received non-zero value",
                    })

            # --- String: case-sensitive equality ---
            elif isinstance(expected, str) and isinstance(actual, str):
                if expected != actual:
                    breaches.append({
                        "field": key,
                        "expected": expected,
                        "actual": actual,
                        "reason": "string value mismatch",
                    })

            # --- Type mismatch (catches bool vs int, list vs dict, etc.) ---
            elif type(expected) is not type(actual):
                breaches.append({
                    "field": key,
                    "expected": expected,
                    "actual": actual,
                    "reason": (
                        f"type mismatch: declared {type(expected).__name__}, "
                        f"received {type(actual).__name__}"
                    ),
                })

            # --- Generic equality (bool, list, dict, None, …) ---
            elif expected != actual:
                breaches.append({
                    "field": key,
                    "expected": expected,
                    "actual": actual,
                    "reason": "value mismatch",
                })

    except Exception:
        logger.exception(
            "_detect_breach: unexpected error comparing intent_details=%r outcome_details=%r",
            intent_details,
            outcome_details,
        )
        return {
            "breach_detected": False,
            "breaches": [],
            "breach_count": 0,
            "severity": "none",
            "_error": "breach detection failed — manual audit required",
        }

    breach_count = len(breaches)
    if breach_count == 0:
        severity = "none"
    elif breach_count <= 2:
        severity = "minor"
    else:
        severity = "major"

    return {
        "breach_detected": breach_count > 0,
        "breaches": breaches,
        "breach_count": breach_count,
        "severity": severity,
    }
