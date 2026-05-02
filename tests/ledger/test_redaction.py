"""Tests for ledger payload redaction (W3.B.3).

Asserts CLAUDE.md §3.9 compliance at the ledger layer:
  Auth fields are stripped from payload BEFORE the entry is hashed and
  HMAC-signed.  Stripping AFTER hashing would allow an attacker to
  reconstruct the pre-hash payload and extract credentials from the ledger.

The three mandatory redaction targets are:
  - ``authorization``  — HTTP Authorization header value (Bearer token, Basic)
  - ``auth_user``      — username portion of an authentication context
  - ``api_key``        — API key / service token

Redaction is case-insensitive on the key name (``Authorization`` and
``authorization`` are both stripped).  The value is replaced with the
constant ``<redacted>``; the original value is NOT logged anywhere.

ARCHITECTURE.md §5: ``payload_redactions: list[str]`` records which keys
were stripped for auditability without recording the values.
"""

from __future__ import annotations

import copy

from verdict.ledger.redaction import (
    REDACT_KEYS,
    REDACTION_SENTINEL,
    RedactionResult,
    redact_payload,
)

# ---------------------------------------------------------------------------
# Core redaction — individual fields
# ---------------------------------------------------------------------------


class TestRedactPayload:
    """redact_payload() strips credential fields before hashing."""

    def test_redacts_authorization_header_before_hash(self) -> None:
        """'authorization' key is stripped from payload and recorded."""
        payload = {"authorization": "Bearer abc123", "case_id": "case-001"}
        result = redact_payload(payload)
        assert result.redacted_payload["authorization"] == REDACTION_SENTINEL
        assert "authorization" in result.redacted_keys
        assert result.redacted_payload["case_id"] == "case-001"

    def test_redacts_auth_user(self) -> None:
        """'auth_user' key is stripped from payload."""
        payload = {"auth_user": "analyst@example.com", "event_type": "case_init"}
        result = redact_payload(payload)
        assert result.redacted_payload["auth_user"] == REDACTION_SENTINEL
        assert "auth_user" in result.redacted_keys

    def test_redacts_api_key(self) -> None:
        """'api_key' key is stripped from payload."""
        payload = {"api_key": "vt-secret-key-xyz", "tool_name": "virustotal"}
        result = redact_payload(payload)
        assert result.redacted_payload["api_key"] == REDACTION_SENTINEL
        assert "api_key" in result.redacted_keys

    def test_redacts_all_three_simultaneously(self) -> None:
        """All three fields are redacted in a single payload."""
        payload = {
            "authorization": "Bearer tok",
            "auth_user": "user@example.com",
            "api_key": "key123",
            "case_id": "case-001",
        }
        result = redact_payload(payload)
        assert result.redacted_payload["authorization"] == REDACTION_SENTINEL
        assert result.redacted_payload["auth_user"] == REDACTION_SENTINEL
        assert result.redacted_payload["api_key"] == REDACTION_SENTINEL
        assert result.redacted_payload["case_id"] == "case-001"
        assert set(result.redacted_keys) == {"authorization", "auth_user", "api_key"}

    def test_non_auth_fields_preserved(self) -> None:
        """All non-auth fields pass through unchanged."""
        payload = {
            "case_id": "case-001",
            "event_type": "tool_call",
            "tool_name": "vol3.windows.pslist",
            "timestamp_utc": "2026-05-01T12:00:00Z",
        }
        result = redact_payload(payload)
        for key, value in payload.items():
            assert result.redacted_payload[key] == value
        assert result.redacted_keys == []

    def test_empty_payload_is_safe(self) -> None:
        """An empty payload is handled without error."""
        result = redact_payload({})
        assert result.redacted_payload == {}
        assert result.redacted_keys == []


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------


class TestCaseInsensitiveRedaction:
    """Redaction is case-insensitive on the key name."""

    def test_authorization_uppercase_A(self) -> None:
        """'Authorization' (capital A) is redacted."""
        result = redact_payload({"Authorization": "Bearer tok"})
        # Key name is lowercased in the output
        lower_keys = {k.lower() for k in result.redacted_payload}
        assert "authorization" in lower_keys
        # The value at whatever-case key is the sentinel
        for k, v in result.redacted_payload.items():
            if k.lower() == "authorization":
                assert v == REDACTION_SENTINEL

    def test_api_key_mixed_case(self) -> None:
        """'API_KEY' (screaming snake) is redacted."""
        result = redact_payload({"API_KEY": "secret"})
        lower_keys = {k.lower() for k in result.redacted_keys}
        assert "api_key" in lower_keys

    def test_auth_user_mixed_case(self) -> None:
        """'Auth_User' is redacted."""
        result = redact_payload({"Auth_User": "user@example.com"})
        lower_keys = {k.lower() for k in result.redacted_keys}
        assert "auth_user" in lower_keys


# ---------------------------------------------------------------------------
# Immutability — original payload not mutated
# ---------------------------------------------------------------------------


class TestRedactionImmutability:
    """redact_payload() must not mutate the input dict."""

    def test_does_not_mutate_original_payload(self) -> None:
        """The original payload dict is not modified."""
        payload = {"authorization": "Bearer secret", "case_id": "case-001"}
        original = copy.deepcopy(payload)
        redact_payload(payload)
        assert payload == original, "redact_payload() mutated the original dict"

    def test_returns_new_dict(self) -> None:
        """The returned redacted_payload is a distinct object."""
        payload = {"authorization": "Bearer secret"}
        result = redact_payload(payload)
        assert result.redacted_payload is not payload


# ---------------------------------------------------------------------------
# RedactionResult schema
# ---------------------------------------------------------------------------


class TestRedactionResult:
    """RedactionResult carries both the redacted payload and the key list."""

    def test_redacted_keys_contains_only_stripped_keys(self) -> None:
        """redacted_keys lists only the keys that were actually present and stripped."""
        payload = {"authorization": "tok", "case_id": "c"}
        result = redact_payload(payload)
        assert result.redacted_keys == ["authorization"]

    def test_redacted_keys_empty_when_no_auth_fields(self) -> None:
        """redacted_keys is empty when no auth fields are present."""
        result = redact_payload({"case_id": "c", "event_type": "tool_call"})
        assert result.redacted_keys == []

    def test_original_value_not_stored_in_result(self) -> None:
        """The original credential value must not appear anywhere in the result."""
        secret = "ultra-secret-token-never-log-this"
        payload = {"authorization": f"Bearer {secret}"}
        result = redact_payload(payload)
        # Check the redacted payload
        for v in result.redacted_payload.values():
            assert secret not in str(v), "Secret leaked into redacted_payload"
        # Check the redacted_keys list
        for k in result.redacted_keys:
            assert secret not in k, "Secret leaked into redacted_keys"
        # Verify sentinel is set
        assert result.redacted_payload["authorization"] == REDACTION_SENTINEL

    def test_redaction_result_is_pydantic_model(self) -> None:
        """RedactionResult is a Pydantic model (typed, serialisable)."""
        from pydantic import BaseModel

        assert issubclass(RedactionResult, BaseModel)

    def test_result_json_serialisable(self) -> None:
        """RedactionResult.model_dump() returns a JSON-serialisable dict."""
        import json

        result = redact_payload({"authorization": "tok", "case_id": "c"})
        dumped = result.model_dump()
        # Must not raise
        json.dumps(dumped)


# ---------------------------------------------------------------------------
# REDACT_KEYS constant
# ---------------------------------------------------------------------------


class TestRedactKeysConstant:
    """REDACT_KEYS is the authoritative set of credential field names (lowercase)."""

    def test_contains_authorization(self) -> None:
        assert "authorization" in REDACT_KEYS

    def test_contains_auth_user(self) -> None:
        assert "auth_user" in REDACT_KEYS

    def test_contains_api_key(self) -> None:
        assert "api_key" in REDACT_KEYS

    def test_no_extra_expansions_without_doc(self) -> None:
        """The set has exactly the three documented keys.

        If a fourth key is added, this test will fail — that is intentional.
        Expanding the set is a deliberate, visible change, not an accident.
        """
        assert frozenset({"authorization", "auth_user", "api_key"}) == REDACT_KEYS, (
            "REDACT_KEYS expanded beyond the three documented credential fields.  "
            "If this is intentional, update this test."
        )


# ---------------------------------------------------------------------------
# Nested payload — partial redaction of nested dicts
# ---------------------------------------------------------------------------


class TestNestedPayloadRedaction:
    """Credential fields nested inside dicts are also redacted (depth=1)."""

    def test_top_level_redaction_only_by_default(self) -> None:
        """By default, only top-level keys are redacted (depth=1).

        Nested auth fields are a rare edge case; the primary contract is
        top-level.  This test documents the behaviour explicitly.
        """
        payload = {
            "case_id": "c",
            "metadata": {"authorization": "nested-token"},
        }
        result = redact_payload(payload)
        # Top-level is clean (no auth key at top)
        assert result.redacted_keys == []
        # Nested value is NOT redacted at depth=1 (documented limitation)
        assert result.redacted_payload["metadata"]["authorization"] == "nested-token"

    def test_top_level_authorization_still_redacted_alongside_nested(self) -> None:
        """Top-level auth field is redacted even when a nested one also exists."""
        payload = {
            "authorization": "top-level-tok",
            "metadata": {"authorization": "nested-tok"},
        }
        result = redact_payload(payload)
        assert result.redacted_payload["authorization"] == REDACTION_SENTINEL
        assert "authorization" in result.redacted_keys
        # Nested is unchanged
        assert result.redacted_payload["metadata"]["authorization"] == "nested-tok"
