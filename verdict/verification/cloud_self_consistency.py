"""W1.C.2 — n=3 cloud self-consistency strategy.

Wang et al. 2022 self-consistency (arXiv:2203.11171) requires *diverse*
reasoning paths.  The previous v4.5 design used ``temperature=0`` with
"different seeds", which is a contradiction in terms — at ``temperature=0``
the sampler is greedy and the seed is irrelevant, so the n=3 quorum
collapses to n=1 and the strategy provides zero verification value.

v4.6 Patch F1 fixes this:

- ``temperature = 0.7`` on every sample (never 0; never 1+).
- Three distinct seeds derived from ``case_id`` via blake3 keyed-hash
  (``verdict.verification.derive_seeds``). Same case_id always yields
  the same trio (audit-replay), but the trio members differ from each
  other (verifier-friendly diversity).
- Each seed is anchored *in the user prompt* via a ``<sample_seed>``
  tag, not just in API metadata. Anthropic's public Messages API does
  not expose a server-side ``seed`` parameter (verified against
  ``anthropic`` SDK 0.97.0 — the kwargs are
  ``{max_tokens, messages, model, cache_control, container,
  inference_geo, metadata, output_config, service_tier, stop_sequences,
  stream, system, temperature, thinking, tool_choice, tools, top_k,
  top_p, ...}``). Salting the prompt makes the divergence wire-visible
  and immune to transparent caching layers that key on prompt hash.
- The strategy also stamps ``metadata.user_id`` with the seed so the
  three sibling spans are visible in Langfuse / Anthropic trace tooling
  as distinct calls (CLAUDE.md §11 — the demo shows three sibling
  spans).

This is **best-effort vetting, not true verification**: same model
shares failure modes. The strategy returns ``VETTED_CLOUD`` on
≥ 2-of-3 agreement; below threshold escalates to ``CONTESTED`` ->
``replan_node`` (ARCHITECTURE.md §1 quorum dispatch). The agreement
check itself is wired by ``W3.A.1`` (verifier_quorum) and is not
implemented in this file — this file owns the *seed-derivation +
request-construction* layer per BUILD_PLAN W1.C.2.

Why a separate ``build_call_payloads`` method? Two reasons:

1. **Testability without mocks.** CLAUDE.md §3.10 forbids
   ``MockLLM`` / ``StubAnthropic`` against verdict internals. The
   distinctness invariant is a property of the request-construction
   layer, which is a pure function on its inputs and can be unit-
   tested without instantiating an HTTP client.
2. **Determinism boundary.** Everything before the network is
   reproducible from ``case_id`` alone; everything after the network
   is whatever the model returned. Splitting the two lets the ledger
   replay payload-construction during ``verdict validate`` without
   re-incurring API spend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from verdict.verification.derive_seeds import derive_seeds

# v4.6 Patch F1 contract: ``temperature == 0.7`` on every sample. Bumping
# this is a coordinated change to the audit doc + a new verifier strategy
# version, not a tweak.
DEFAULT_TEMPERATURE: float = 0.7

# Three samples per Wang et al. 2022 + the v4.6 schema. Bumping to n=5
# requires a separate RFC; the ledger / quorum dispatch tables hard-code
# the trio assumption.
N_SAMPLES: int = 3

# Default model. Concretely pinned so a wire-level recording in the
# ledger can be replayed against the same model family. The CLI surface
# (``verdict init``) may override via config, but this is the default.
DEFAULT_MODEL: str = "claude-opus-4-5"

# Max tokens per sample. Findings are short; cap to bound spend.
DEFAULT_MAX_TOKENS: int = 4096


class InvalidTemperatureError(ValueError):
    """Raised when ``CloudSelfConsistency`` is constructed with an out-of-range
    temperature.

    ``temperature == 0`` is the load-bearing failure mode (Wang 2022 §3 —
    diverse-path requirement); we also reject negatives and values > 1
    because they are programming errors at the gateway layer rather than
    legitimate sampling regimes.
    """


@dataclass(frozen=True)
class CloudSelfConsistency:
    """n=3 cloud self-consistency strategy (cloud-only mode).

    Parameters
    ----------
    temperature:
        Sampling temperature. Must satisfy ``0 < temperature <= 1``.
        Defaults to ``0.7`` (v4.6 Patch F1).
    model:
        Anthropic model name. Defaults to ``DEFAULT_MODEL``.
    max_tokens:
        Max tokens per sample. Defaults to ``DEFAULT_MAX_TOKENS``.

    Raises
    ------
    InvalidTemperatureError
        On any temperature outside ``(0, 1]``.
    """

    temperature: float = DEFAULT_TEMPERATURE
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    # ClassVar so N_SAMPLES is excluded from __init__: calling
    # CloudSelfConsistency(N_SAMPLES=5) raises TypeError at construction time
    # rather than silently creating an instance where self.N_SAMPLES != len(seeds).
    N_SAMPLES: ClassVar[int] = 3

    def __post_init__(self) -> None:
        if not (0.0 < self.temperature <= 1.0):
            raise InvalidTemperatureError(
                f"temperature must satisfy 0 < temp <= 1; got {self.temperature!r}. "
                "temperature=0 collapses n=3 to n=1 (Wang et al. 2022); "
                "values >1 are non-physical for the Anthropic API."
            )

    def build_call_payloads(
        self,
        case_id: str,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
    ) -> list[dict]:
        """Build three sibling Anthropic ``messages.create`` payloads.

        Each payload carries one of the three blake3-derived seeds
        salted into the user message and stamped on ``metadata.user_id``,
        plus the load-bearing ``temperature=self.temperature``.

        The returned list is a plain ``list[dict]`` so the caller can
        ``await client.messages.create(**payload)`` directly. The
        dict also carries a ``_verdict_seed`` field (with the leading
        underscore to mark it as not-for-the-wire) so the
        ``LedgerEmitter`` can record which seed produced which sample
        without reconstructing the trio. The transport layer
        (W3.A.1 verifier_quorum) is responsible for stripping the
        underscore-prefixed fields before passing kwargs to the
        Anthropic SDK.

        Parameters
        ----------
        case_id:
            Case identifier; passed to ``derive_seeds`` to anchor the
            three seeds.
        hypothesis:
            The hypothesis text under verification (e.g.
            "Evidence consistent with rundll32 invoking ...").
        mitre_technique:
            MITRE ATT&CK technique ID (e.g. "T1003.001"). Format
            validated upstream by the ``Hypothesis`` schema.
        evidence_summary:
            Compact summary of the artifacts the hypothesis cites.

        Returns
        -------
        list[dict]
            ``self.N_SAMPLES`` deterministic, distinct request payloads.
        """
        seeds = derive_seeds(case_id)
        return [
            self._build_one(
                case_id=case_id,
                seed=seed,
                hypothesis=hypothesis,
                mitre_technique=mitre_technique,
                evidence_summary=evidence_summary,
            )
            for seed in seeds
        ]

    def _build_one(
        self,
        *,
        case_id: str,
        seed: int,
        hypothesis: str,
        mitre_technique: str,
        evidence_summary: str,
    ) -> dict:
        """Build a single payload for sample ``seed`` of the n=3 trio."""
        user_content = (
            f"<sample_seed>{seed}</sample_seed>\n"
            f"<case_id>{case_id}</case_id>\n"
            f"<hypothesis mitre_technique=\"{mitre_technique}\">\n"
            f"{hypothesis}\n"
            f"</hypothesis>\n"
            f"<evidence_summary>\n{evidence_summary}\n</evidence_summary>\n"
            "Independently verify the hypothesis against the evidence. "
            'Phrase your verdict as "evidence consistent with X" or '
            '"evidence inconsistent with X" -- never "X did this". '
            "Conclude with a JSON object on its own line: "
            '{"verdict": "consistent|inconsistent|unverifiable", '
            '"mitre_technique": "<TID or null>", '
            '"parsed_artifacts": ["<path1>", "<path2>", ...]}'
        )
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": user_content}],
            "metadata": {"user_id": f"verdict-{case_id}-seed-{seed}"},
            # Underscore-prefixed: not sent over the wire by the
            # transport layer; recorded in the ledger as part of the
            # sample's audit metadata.
            "_verdict_seed": seed,
            "_verdict_sample_n": N_SAMPLES,
        }
