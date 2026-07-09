"""Unit tests for utils breach detection and hash determinism."""

from utils import (
    _compute_binding_hash,
    _compute_hash,
    _compute_intent_hash,
    _detect_breach,
)


class TestDetectBreachClean:
    def test_identical_details_no_breach(self):
        details = {"amount": 100, "currency": "USD"}
        result = _detect_breach(details, dict(details))
        assert result["breach_detected"] is False
        assert result["breach_count"] == 0
        assert result["severity"] == "none"

    def test_extra_outcome_keys_ignored(self):
        result = _detect_breach(
            {"amount": 100},
            {"amount": 100, "invoice": "INV-1", "note": "extra info is legal"},
        )
        assert result["breach_detected"] is False

    def test_numeric_within_tolerance_no_breach(self):
        # 4% deviation is under the 5% tolerance
        result = _detect_breach({"amount": 100}, {"amount": 104})
        assert result["breach_detected"] is False


class TestDetectBreachViolations:
    def test_omitted_field_is_breach(self):
        result = _detect_breach({"amount": 100}, {})
        assert result["breach_detected"] is True
        assert result["breaches"][0]["reason"] == "field omitted from outcome"

    def test_numeric_deviation_beyond_tolerance(self):
        result = _detect_breach({"amount": 100}, {"amount": 200})
        assert result["breach_detected"] is True
        assert "tolerance" in result["breaches"][0]["reason"]

    def test_expected_zero_actual_nonzero(self):
        result = _detect_breach({"fee": 0}, {"fee": 5})
        assert result["breach_detected"] is True
        assert "zero" in result["breaches"][0]["reason"]

    def test_string_mismatch(self):
        result = _detect_breach({"currency": "USD"}, {"currency": "EUR"})
        assert result["breach_detected"] is True
        assert result["breaches"][0]["reason"] == "string value mismatch"

    def test_bool_value_mismatch(self):
        result = _detect_breach({"recurring": True}, {"recurring": False})
        assert result["breach_detected"] is True
        assert result["breaches"][0]["reason"] == "boolean value mismatch"

    def test_bool_vs_int_type_mismatch(self):
        # bool is a subclass of int; must be flagged as a type mismatch, not equality
        result = _detect_breach({"recurring": True}, {"recurring": 1})
        assert result["breach_detected"] is True
        assert "type mismatch" in result["breaches"][0]["reason"]

    def test_type_mismatch_list_vs_dict(self):
        result = _detect_breach({"items": [1, 2]}, {"items": {"a": 1}})
        assert result["breach_detected"] is True
        assert "type mismatch" in result["breaches"][0]["reason"]

    def test_generic_mismatch_lists(self):
        result = _detect_breach({"items": [1, 2]}, {"items": [1, 3]})
        assert result["breach_detected"] is True
        assert result["breaches"][0]["reason"] == "value mismatch"


class TestDetectBreachSeverity:
    def test_single_breach_is_minor(self):
        result = _detect_breach({"amount": 100}, {"amount": 200})
        assert result["severity"] == "minor"

    def test_three_breaches_is_major(self):
        result = _detect_breach(
            {"amount": 100, "currency": "USD", "recipient": "acme"},
            {"amount": 200, "currency": "EUR", "recipient": "evil-corp"},
        )
        assert result["breach_count"] == 3
        assert result["severity"] == "major"


class TestHashDeterminism:
    def test_compute_hash_key_order_independent(self):
        assert _compute_hash({"b": 2, "a": 1}) == _compute_hash({"a": 1, "b": 2})

    def test_compute_hash_unserialisable_returns_sentinel(self):
        # A set inside an unsortable structure that json cannot handle even
        # with default=str coercion at the top level of keys
        result = _compute_hash({("tuple", "key"): 1})
        assert result == "0" * 64

    def test_intent_hash_deterministic(self):
        h1 = _compute_intent_hash("agent-1", "buy", {"amount": 10})
        h2 = _compute_intent_hash("agent-1", "buy", {"amount": 10})
        assert h1 == h2
        assert len(h1) == 64

    def test_intent_hash_sensitive_to_details(self):
        h1 = _compute_intent_hash("agent-1", "buy", {"amount": 10})
        h2 = _compute_intent_hash("agent-1", "buy", {"amount": 11})
        assert h1 != h2

    def test_binding_hash_binds_both_inputs(self):
        intent = {"intent_id": "abc", "agent_id": "a1"}
        verif = {"verifier_id": "v1", "accepts": True}
        h1 = _compute_binding_hash(intent, verif)
        h2 = _compute_binding_hash(intent, {"verifier_id": "v1", "accepts": False})
        assert h1 != h2
        assert len(h1) == 64
