"""TSI (Token-Secure Injection) Pattern 2 provider — W3.B.1.

Implements ARCHITECTURE.md §3 "Pattern 2 — TSI for credential injection".

Security invariant (CLAUDE.md §3.9):
  API keys, OAuth tokens, and bearer tokens NEVER enter a microVM.  The TSI
  proxy runs on the host and injects the credential header at the host network
  layer (vsock-routed egress).  The raw token is:

    1. Sourced from an environment variable on the host (never a code literal).
    2. Passed to ``inject_header_on_host()`` at the host proxy layer only.
    3. Never included in the ``microsandbox.spawn()`` kwargs (verified by
       ``TSINetworkPolicy.as_spawn_kwargs()`` + the ``TestTSINetworkPolicy``
       unit tests).
    4. Redacted from ``repr()`` so it cannot leak to log output.

How Pattern 2 works (ARCHITECTURE.md §3):
    sandbox = await microsandbox.spawn(
        image="verdict-malware-tools@sha256:<pin>",
        network_policy=TSI(
            proxy_origin="opencti.local:8080",
            inject_header={"Authorization": f"Bearer {os.environ['OPENCTI_KEY']}"},
        ),
    )

The ``TSINetworkPolicy`` in this module encodes the above pattern.  The
microsandbox SDK's ``TSI`` object (``TSIProxy`` here) is passed as the
``network_policy`` kwarg to ``microsandbox.spawn()``.  The proxy origin is
the only allowlisted destination; all other egress is blocked.

For tooling that does not yet have a running Microsandbox installation (W3.B
is parallel to W2.B which wires the full microsandbox SDK call), the
``TSINetworkPolicy`` and ``TSIConfig`` classes provide the full schema and
token-isolation enforcement, while the ``microsandbox.spawn()`` call itself
is deferred to W2.B's wiring (raising ``NotImplementedError`` if called
without a running Microsandbox daemon).

tcpdump proof (docs/DEMO_SEQUENCE.md §B.3 + CLAUDE.md §3.9):
    bearer header present on host egress to opencti.local:8080
    bearer header absent inside the microVM (verified by capture on vsock
    loopback inside the VM)

``run_tsi_microvm_tcpdump_proof()`` is the integration entry-point for this
proof.  It requires a running Microsandbox installation; the corresponding
test in ``tests/sandboxes/test_tsi_provider.py`` is ``pytest.mark.skipif``-
gated on Microsandbox presence per CLAUDE.md §3.10.

Allowed credential header names:
  - ``Authorization``  (Bearer tokens — OpenCTI, abuse.ch, MITRE ATT&CK API)
  - ``X-Api-Key``      (VirusTotal v3 API)
"""

from __future__ import annotations

import copy
import dataclasses
import os
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Credential header names accepted by TSIConfig.  Any other header name is
#: rejected at construction time — TSI only proxies credential headers.
ALLOWED_HEADER_NAMES: Final[frozenset[str]] = frozenset({"Authorization", "X-Api-Key"})

#: Loopback origins that must not be used as proxy_origin.
_LOOPBACK_PREFIXES: Final[tuple[str, ...]] = ("127.", "::1", "localhost")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IsolationViolationError(RuntimeError):
    """Raised when inject_header_on_host() is called with a non-empty vm_env.

    This is the code-path-level enforcement of CLAUDE.md §3.9.  A non-empty
    ``vm_env`` dict indicates the caller is running inside (or simulating the
    inside of) a microVM context; injecting the credential in that context
    would violate the TSI isolation guarantee.
    """


# ---------------------------------------------------------------------------
# TSIConfig — credential + proxy configuration
# ---------------------------------------------------------------------------


class TSIConfig(BaseModel):
    """Configuration for a single TSI-proxied enrichment call.

    Fields
    ------
    proxy_origin
        The single allowlisted egress destination in ``host:port`` form.
        Must not be a loopback address (``127.*``, ``::1``, ``localhost``).
    inject_header
        A single-entry dict of ``{header_name: header_value}``.
        header_name must be one of: ``Authorization``, ``X-Api-Key``.
        The header value (i.e. the raw credential) is stored in-memory but
        **redacted from repr()** so it cannot leak to log output.

    Credential sourcing
    -------------------
    Use ``TSIConfig.from_env()`` to source the token from an environment
    variable.  Never pass a hard-coded string literal as the header value.
    """

    model_config = ConfigDict(frozen=True)

    proxy_origin: str = Field(..., min_length=1)
    inject_header: dict[str, str] = Field(..., min_length=1)

    @field_validator("proxy_origin")
    @classmethod
    def _reject_loopback(cls, v: str) -> str:
        for prefix in _LOOPBACK_PREFIXES:
            if v.lower().startswith(prefix):
                raise ValueError(
                    f"proxy_origin must not be a loopback address; got {v!r}.  "
                    "TSI proxies traffic to an external enrichment service."
                )
        return v

    @field_validator("inject_header")
    @classmethod
    def _require_credential_header(cls, v: dict[str, str]) -> dict[str, str]:
        if not v:
            raise ValueError("inject_header must be non-empty")
        for key in v:
            if key not in ALLOWED_HEADER_NAMES:
                raise ValueError(
                    f"inject_header key {key!r} is not a credential header.  "
                    f"Allowed: {sorted(ALLOWED_HEADER_NAMES)}.  "
                    "TSI only proxies credential headers (Authorization, X-Api-Key)."
                )
        return v

    def __repr__(self) -> str:
        """Redact the credential value from repr() (CLAUDE.md §3.9)."""
        redacted = {k: "<redacted>" for k in self.inject_header}
        return (
            f"TSIConfig(proxy_origin={self.proxy_origin!r}, "
            f"inject_header={redacted!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    # ------------------------------------------------------------------
    # Factory — env-var sourcing
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        proxy_origin: str,
        *,
        header_env_var: str,
        header_name: str = "Authorization",
        bearer_prefix: bool = True,
    ) -> TSIConfig:
        """Construct a TSIConfig sourcing the credential from an environment variable.

        Parameters
        ----------
        proxy_origin
            The single allowlisted egress destination.
        header_env_var
            Name of the environment variable holding the raw token value.
        header_name
            The HTTP header to inject (default ``Authorization``).
        bearer_prefix
            If True and header_name is ``Authorization``, prepend ``Bearer ``
            to the token value.  Set False for pre-formatted values or
            ``X-Api-Key`` headers.

        Raises
        ------
        EnvironmentError
            If ``header_env_var`` is not set in the environment.
        """
        raw_value = os.environ.get(header_env_var)
        if raw_value is None:
            raise OSError(
                f"Environment variable {header_env_var!r} is not set.  "
                "TSI credential injection requires the token to be present in "
                "the host environment.  Set it before starting the verdict runtime."
            )
        if header_name == "Authorization" and bearer_prefix:
            header_value = f"Bearer {raw_value}"
        else:
            header_value = raw_value
        return cls(
            proxy_origin=proxy_origin,
            inject_header={header_name: header_value},
        )


# ---------------------------------------------------------------------------
# TSIProxy — the opaque object passed to microsandbox.spawn()
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TSIProxy:
    """Opaque network policy object consumed by ``microsandbox.spawn()``.

    The Microsandbox SDK's ``network_policy`` kwarg accepts a ``TSIProxy``
    instance.  The proxy origin is the single allowlisted egress destination;
    the credential is injected at the host network layer and is NOT stored
    in this object (the SDK reads it via the host-side TSI daemon).

    Security: this object intentionally does NOT carry the raw token.  The
    host-side TSI daemon holds the credential and injects it into the outbound
    HTTP request *after* the packet leaves the microVM's vsock interface.
    Inspection of this object (e.g., in microVM process environment) yields
    only the allowed origin — not the token.
    """

    allowed_origins: frozenset[str]

    def __repr__(self) -> str:  # pragma: no cover
        return f"TSIProxy(allowed_origins={self.allowed_origins!r})"


# ---------------------------------------------------------------------------
# TSINetworkPolicy — encodes TSIConfig as microsandbox.spawn() kwargs
# ---------------------------------------------------------------------------


class TSINetworkPolicy:
    """Translates a ``TSIConfig`` into ``microsandbox.spawn()`` keyword arguments.

    Usage::

        policy = TSINetworkPolicy(config)
        sandbox = await microsandbox.spawn(
            image="verdict-malware-tools@sha256:<pin>",
            **policy.as_spawn_kwargs(),
        )

    The ``as_spawn_kwargs()`` dict:
    - Contains ``network_policy``: a ``TSIProxy(allowed_origins={origin})``
      instance that the Microsandbox SDK uses to configure the host-side proxy.
    - Does NOT contain ``env``, the raw token, or any credential value.
    - Does NOT contain ``network=True``; the TSI proxy implicitly enables
      vsock-routed egress to the single allowlisted origin only.
    """

    def __init__(self, config: TSIConfig) -> None:
        self._config = config

    def as_spawn_kwargs(self) -> dict:
        """Return the kwargs dict for ``microsandbox.spawn()``.

        Returns
        -------
        dict
            ``{"network_policy": TSIProxy(allowed_origins={proxy_origin})}``

        The raw credential value is intentionally absent from the returned
        dict (CLAUDE.md §3.9).
        """
        return {
            "network_policy": TSIProxy(
                allowed_origins=frozenset({self._config.proxy_origin})
            )
        }


# ---------------------------------------------------------------------------
# inject_header_on_host — host-side header injection
# ---------------------------------------------------------------------------


def inject_header_on_host(
    config: TSIConfig,
    request: dict,
    *,
    vm_env: dict | None = None,
) -> dict:
    """Inject the credential header into an outbound HTTP request at the host layer.

    This function runs on the HOST, never inside a microVM.  The ``vm_env``
    parameter is a safety guard: if it is non-empty, ``IsolationViolationError``
    is raised immediately — a non-empty ``vm_env`` indicates the caller is
    executing in (or simulating) a microVM context, which would violate the
    TSI isolation guarantee.

    Parameters
    ----------
    config
        The TSI configuration holding the proxy origin and credential header.
    request
        A dict with at least ``method``, ``path``, and ``headers`` keys.
        ``headers`` must be a dict; other keys are passed through unchanged.
    vm_env
        If non-empty, raises ``IsolationViolationError``.  Callers inside a
        microVM context must never reach this function.

    Returns
    -------
    dict
        A *copy* of the request dict with the credential header added to
        ``headers``.  The original dict is not mutated.

    Raises
    ------
    IsolationViolationError
        If ``vm_env`` is non-empty (CLAUDE.md §3.9 hard gate).
    """
    if vm_env:
        raise IsolationViolationError(
            "inject_header_on_host() must not be called from inside a microVM "
            "context.  A non-empty vm_env was supplied, which indicates an "
            "isolation violation.  CLAUDE.md §3.9: bearer tokens never enter "
            "a microVM."
        )

    # Deep-copy so the original dict is not mutated
    enriched = copy.deepcopy(request)
    enriched["headers"] = dict(enriched.get("headers", {}))
    enriched["headers"].update(config.inject_header)
    return enriched


# ---------------------------------------------------------------------------
# run_tsi_microvm_tcpdump_proof — integration entry-point for tcpdump assertion
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TcpdumpProofResult:
    """Result of the tcpdump-based TSI proof.

    Attributes
    ----------
    host_egress_bearer_count
        Number of HTTP frames on the host egress interface that contain an
        ``Authorization: Bearer`` header targeting the proxy origin.
    vm_internal_bearer_count
        Number of HTTP frames captured on the VM-internal vsock loopback that
        contain an ``Authorization: Bearer`` header.  Must be zero for §3.9
        compliance.
    """

    host_egress_bearer_count: int
    vm_internal_bearer_count: int


def run_tsi_microvm_tcpdump_proof(
    *,
    proxy_origin: str,
    header_env_var: str,
) -> TcpdumpProofResult:
    """Run a real Microsandbox microVM and capture traffic to prove §3.9 compliance.

    This function:
    1. Sources the credential from the environment variable ``header_env_var``.
    2. Spawns a microVM with ``TSINetworkPolicy`` targeting ``proxy_origin``.
    3. Starts tcpdump captures on both the host egress interface and the
       VM-internal vsock loopback.
    4. Issues a synthetic HTTP GET to ``proxy_origin`` from inside the VM
       (via the TSI proxy).
    5. Returns ``TcpdumpProofResult`` with the bearer header counts.

    Requirements:
    - Microsandbox installed (``msb`` binary present).
    - ``header_env_var`` set in the host environment.
    - ``proxy_origin`` reachable from the host.

    This function raises ``NotImplementedError`` if Microsandbox is not
    available.  The corresponding test is ``pytest.mark.skipif``-gated on
    Microsandbox presence (CLAUDE.md §3.10: skip ≠ pass; the CI Microsandbox
    runner will execute it against a real microVM).
    """
    import shutil

    if not shutil.which("msb") and not os.path.exists(
        os.path.expanduser("~/.microsandbox/bin/msb")
    ):
        raise NotImplementedError(
            "Microsandbox is not installed.  "
            "Install via: curl -sSL https://get.microsandbox.dev | sh"
        )

    # The full tcpdump + spawn integration is wired in W2.B (microsandbox SDK
    # wiring).  This stub raises NotImplementedError until that wiring lands.
    # Per CLAUDE.md §3.10: raising NotImplementedError on an unimplemented
    # *real* method is correct; do not return synthetic data.
    raise NotImplementedError(
        "run_tsi_microvm_tcpdump_proof() requires the Microsandbox SDK spawn "
        "integration from W2.B.  Wire verdict/sandboxes/microsandbox_provider.py "
        "first, then implement the tcpdump capture loop here."
    )
