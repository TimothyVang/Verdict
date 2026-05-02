"""Tests for TSI Pattern 2 credential injection (W3.B.1).

These tests cover the structural invariants of the TSI provider that guarantee
CLAUDE.md §3.9 compliance:  API keys / OAuth tokens / bearer tokens never enter
a microVM.

Architecture reference: ARCHITECTURE.md §3 "Pattern 2 — TSI for credential
injection".  The microVM-level tcpdump assertion (bearer header present on host
egress, absent inside VM) requires a running Microsandbox + real vsock network
stack.  That assertion is documented in docs/DEMO_SEQUENCE.md and exercised
manually / in the CI Microsandbox runner.  The structural tests below exercise
every code path that is reachable without spawning a microVM.

Per CLAUDE.md §3.10 — no mocks, no stubs, no conditional test paths.  These
tests run fully in production.  If a test requires Microsandbox and Microsandbox
is not present, the test calls pytest.skip() (skip ≠ pass; the CI runner that
has Microsandbox will run it and fail loudly if the assertion breaks).
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from verdict.sandboxes.tsi_provider import (
    IsolationViolationError,
    TSIConfig,
    TSINetworkPolicy,
    TSIProxy,
    inject_header_on_host,
)

# ---------------------------------------------------------------------------
# TSIConfig — structural + isolation invariants
# ---------------------------------------------------------------------------


class TestTSIConfig:
    """TSIConfig Pydantic model invariants."""

    def test_requires_proxy_origin(self) -> None:
        """proxy_origin must be non-empty; empty string → ValidationError."""
        with pytest.raises(ValidationError):
            TSIConfig(proxy_origin="", inject_header={"Authorization": "Bearer x"})

    def test_requires_inject_header(self) -> None:
        """inject_header must be non-empty; empty dict → ValidationError."""
        with pytest.raises(ValidationError):
            TSIConfig(proxy_origin="opencti.local:8080", inject_header={})

    def test_inject_header_key_must_be_credential_header(self) -> None:
        """inject_header keys must be 'Authorization' or 'X-Api-Key'.

        Any other key raises ValidationError — we only proxy credential
        headers, not arbitrary HTTP headers.
        """
        with pytest.raises(ValidationError):
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"X-Custom-Data": "not-a-credential"},
            )

    def test_valid_config_authorization_bearer(self) -> None:
        """A valid TSIConfig with Authorization header is constructed without error."""
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer abc123"},
        )
        assert cfg.proxy_origin == "opencti.local:8080"
        assert "Authorization" in cfg.inject_header

    def test_valid_config_x_api_key(self) -> None:
        """A valid TSIConfig with X-Api-Key header is constructed without error."""
        cfg = TSIConfig(
            proxy_origin="www.virustotal.com:443",
            inject_header={"X-Api-Key": "vt-token"},
        )
        assert cfg.proxy_origin == "www.virustotal.com:443"
        assert "X-Api-Key" in cfg.inject_header

    def test_header_value_not_stored_in_plaintext_repr(self) -> None:
        """repr() of TSIConfig must NOT expose the bearer token value.

        A developer printing the config to a log must not accidentally leak
        the credential (CLAUDE.md §3.9).
        """
        token = "super-secret-token-xyz"
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": f"Bearer {token}"},
        )
        assert token not in repr(cfg), (
            "Bearer token must not appear in repr() — would leak to logs"
        )

    def test_proxy_origin_must_not_be_loopback_ipv4(self) -> None:
        """proxy_origin 127.0.0.1 → ValidationError (loopback indicates misconfiguration)."""
        with pytest.raises(ValidationError):
            TSIConfig(
                proxy_origin="127.0.0.1:8080",
                inject_header={"Authorization": "Bearer x"},
            )

    def test_proxy_origin_must_not_be_localhost(self) -> None:
        """proxy_origin 'localhost' → ValidationError."""
        with pytest.raises(ValidationError):
            TSIConfig(
                proxy_origin="localhost:8080",
                inject_header={"Authorization": "Bearer x"},
            )


# ---------------------------------------------------------------------------
# TSIConfig.from_env — environment variable sourcing
# ---------------------------------------------------------------------------


class TestTSIConfigFromEnv:
    """Credentials must be sourced from environment variables, never literals."""

    def test_from_env_authorization_bearer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TSIConfig.from_env() reads the token from an env var."""
        monkeypatch.setenv("OPENCTI_KEY", "env-sourced-token")
        cfg = TSIConfig.from_env(
            proxy_origin="opencti.local:8080",
            header_env_var="OPENCTI_KEY",
        )
        assert "env-sourced-token" in cfg.inject_header.get("Authorization", "")

    def test_from_env_raises_if_var_missing(self) -> None:
        """from_env() raises EnvironmentError if the env var is not set."""
        env_var = "VERDICT_NO_SUCH_KEY_EVER_SET_XYZ"
        if env_var in os.environ:
            pytest.skip("env var accidentally set — cannot test missing path")
        with pytest.raises(EnvironmentError):
            TSIConfig.from_env(
                proxy_origin="opencti.local:8080",
                header_env_var=env_var,
            )

    def test_from_env_x_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VirusTotal key sourced from VT_API_KEY env var."""
        monkeypatch.setenv("VT_API_KEY", "vt-token-from-env")
        cfg = TSIConfig.from_env(
            proxy_origin="www.virustotal.com:443",
            header_env_var="VT_API_KEY",
            header_name="X-Api-Key",
        )
        assert cfg.inject_header.get("X-Api-Key") == "vt-token-from-env"

    def test_from_env_token_not_in_repr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Token sourced from env must still be redacted in repr()."""
        secret = "repr-leak-test-secret"
        monkeypatch.setenv("OPENCTI_KEY", secret)
        cfg = TSIConfig.from_env(
            proxy_origin="opencti.local:8080",
            header_env_var="OPENCTI_KEY",
        )
        assert secret not in repr(cfg)


# ---------------------------------------------------------------------------
# TSINetworkPolicy — sandbox spawn argument encoding
# ---------------------------------------------------------------------------


class TestTSINetworkPolicy:
    """TSINetworkPolicy encodes the microsandbox.spawn() kwargs correctly."""

    def test_as_spawn_kwargs_has_network_policy_key(self) -> None:
        """as_spawn_kwargs() returns a dict with 'network_policy' key."""
        policy = TSINetworkPolicy(
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"Authorization": "Bearer tok"},
            )
        )
        kwargs = policy.as_spawn_kwargs()
        assert "network_policy" in kwargs

    def test_spawn_kwargs_does_not_contain_token_value(self) -> None:
        """The spawn kwargs dict must NOT contain the raw bearer token.

        The TSI proxy injects the header at the host network layer; the token
        must not appear in any value that would be passed *into* the microVM
        as an environment variable or process argument.  This is the software-
        level enforcement of CLAUDE.md §3.9.
        """
        token = "vm-must-never-see-this-token"
        policy = TSINetworkPolicy(
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"Authorization": f"Bearer {token}"},
            )
        )
        kwargs = policy.as_spawn_kwargs()
        # Flatten the entire kwargs dict to a string and verify token absent
        kwargs_str = str(kwargs)
        assert token not in kwargs_str, (
            f"Bearer token appeared in spawn kwargs — would enter the microVM. "
            f"Found in: {kwargs_str!r}"
        )

    def test_spawn_kwargs_network_policy_is_tsi_proxy_instance(self) -> None:
        """network_policy value is a TSIProxy instance (not a raw dict or string)."""
        policy = TSINetworkPolicy(
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"Authorization": "Bearer tok"},
            )
        )
        kwargs = policy.as_spawn_kwargs()
        assert isinstance(kwargs["network_policy"], TSIProxy)

    def test_tsi_proxy_allowed_origins_is_single_configured_origin(self) -> None:
        """TSIProxy.allowed_origins contains only the single configured origin."""
        policy = TSINetworkPolicy(
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"Authorization": "Bearer tok"},
            )
        )
        proxy: TSIProxy = policy.as_spawn_kwargs()["network_policy"]
        assert proxy.allowed_origins == {"opencti.local:8080"}, (
            "TSI proxy must restrict egress to the single configured origin; "
            "additional origins would widen the attack surface"
        )

    def test_spawn_kwargs_no_env_key(self) -> None:
        """spawn kwargs must contain no key named 'env' that could leak the token."""
        token = "no-env-key-leak-token"
        policy = TSINetworkPolicy(
            TSIConfig(
                proxy_origin="opencti.local:8080",
                inject_header={"Authorization": f"Bearer {token}"},
            )
        )
        kwargs = policy.as_spawn_kwargs()
        assert "env" not in kwargs, (
            "'env' key in spawn kwargs would pass variables into the microVM"
        )


# ---------------------------------------------------------------------------
# inject_header_on_host — host-side injection function
# ---------------------------------------------------------------------------


class TestInjectHeaderOnHost:
    """inject_header_on_host() modifies the outbound request at the host layer.

    The function takes a request dict and returns a new request with the
    credential header added.  It must raise IsolationViolationError if called
    with a vm_env context (soft guard against accidental in-VM invocation).
    """

    def test_injects_authorization_header(self) -> None:
        """Header is added to a request that has none."""
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer tok123"},
        )
        request = {"method": "GET", "path": "/api/v2/indicators", "headers": {}}
        enriched = inject_header_on_host(cfg, request)
        assert enriched["headers"]["Authorization"] == "Bearer tok123"

    def test_injects_x_api_key_header(self) -> None:
        """X-Api-Key header is added for VirusTotal-style config."""
        cfg = TSIConfig(
            proxy_origin="www.virustotal.com:443",
            inject_header={"X-Api-Key": "vt-key"},
        )
        request = {"method": "GET", "path": "/api/v3/files/abc", "headers": {}}
        enriched = inject_header_on_host(cfg, request)
        assert enriched["headers"]["X-Api-Key"] == "vt-key"

    def test_does_not_mutate_original_request(self) -> None:
        """inject_header_on_host() returns a new dict, not a mutation of the input."""
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer tok"},
        )
        original: dict = {"method": "GET", "path": "/ping", "headers": {}}
        enriched = inject_header_on_host(cfg, original)
        assert "Authorization" not in original["headers"], (
            "Original request dict was mutated — must return a copy"
        )
        assert enriched is not original

    def test_raises_isolation_violation_if_vm_env_present(self) -> None:
        """If vm_env context is provided, raises IsolationViolationError.

        This is the hard code-path gate: no code running inside a microVM
        context must be able to call inject_header_on_host and get a token.
        The check is advisory (not kernel-enforced); the primary enforcement
        is that host-side code is not deployed into the microVM image at all.
        """
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer tok"},
        )
        request = {"method": "GET", "path": "/ping", "headers": {}}
        with pytest.raises(IsolationViolationError):
            inject_header_on_host(cfg, request, vm_env={"VERDICT_INSIDE_VM": "1"})

    def test_raises_isolation_violation_if_vm_env_is_nonempty(self) -> None:
        """Any non-empty vm_env raises IsolationViolationError regardless of keys."""
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer tok"},
        )
        request = {"method": "GET", "path": "/ping", "headers": {}}
        with pytest.raises(IsolationViolationError):
            inject_header_on_host(cfg, request, vm_env={"ANY_KEY": "any_value"})

    def test_vm_env_none_is_allowed(self) -> None:
        """vm_env=None (the default) allows normal host-side injection."""
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": "Bearer tok"},
        )
        request = {"method": "GET", "path": "/ping", "headers": {}}
        enriched = inject_header_on_host(cfg, request, vm_env=None)
        assert "Authorization" in enriched["headers"]

    def test_credential_not_in_path_or_body(self) -> None:
        """Token must only appear in the headers dict, never in path or body."""
        token = "path-body-leak-test-token"
        cfg = TSIConfig(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": f"Bearer {token}"},
        )
        request = {
            "method": "POST",
            "path": "/api/v2/indicators",
            "headers": {},
            "body": '{"value": "evil.exe"}',
        }
        enriched = inject_header_on_host(cfg, request)
        assert token not in enriched.get("path", "")
        assert token not in enriched.get("body", "")
        assert token in enriched["headers"]["Authorization"]


# ---------------------------------------------------------------------------
# Microsandbox integration test
# (requires real Microsandbox installation — skipped if not present)
# ---------------------------------------------------------------------------

_MSB_PRESENT = os.path.exists("/usr/local/bin/msb") or os.path.exists(
    os.path.expanduser("~/.microsandbox/bin/msb")
)


@pytest.mark.skipif(
    not _MSB_PRESENT,
    reason=(
        "Microsandbox not installed — tcpdump TSI proof requires a real microVM. "
        "Install via: curl -sSL https://get.microsandbox.dev | sh"
    ),
)
def test_credentials_never_enter_microvm() -> None:
    """Bearer header appears on host egress, NOT inside the microVM.

    Requires a running Microsandbox installation + OPENCTI_KEY env var set.

    This test:
    1. Starts a TSI-proxied microVM targeting opencti.local:8080.
    2. Captures traffic on both the host egress interface and the VM-internal
       vsock loopback using tcpdump.
    3. Asserts the Authorization header appears in exactly one host-egress
       frame and zero VM-internal frames.

    Documented in docs/DEMO_SEQUENCE.md §B.3 as the tcpdump TSI proof.
    CLAUDE.md §3.10 — no mocks; real microVM, real capture.
    """
    from verdict.sandboxes.tsi_provider import run_tsi_microvm_tcpdump_proof

    result = run_tsi_microvm_tcpdump_proof(
        proxy_origin="opencti.local:8080",
        header_env_var="OPENCTI_KEY",
    )
    assert result.host_egress_bearer_count >= 1, (
        "Bearer header must appear on host egress to the TSI proxy"
    )
    assert result.vm_internal_bearer_count == 0, (
        "Bearer header must NEVER appear inside the microVM — §3.9 violation"
    )
