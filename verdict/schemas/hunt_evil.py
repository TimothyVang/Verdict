"""verdict/schemas/hunt_evil.py — HuntEvilBaseline + ProcessBaselineAnomaly.

HuntEvilBaseline encodes the expected process characteristics (parent, path,
signing, instance count) for the 8 canonical Windows processes from the
"Hunt Evil" baseline methodology (SANS SEC504/FOR508).

ProcessBaselineAnomaly is a Hypothesis subtype emitted when a process deviates
from its HuntEvilBaseline. It always maps to T1036.005 (Match Legitimate Name
or Location) — the MITRE sub-technique for process masquerading.

Schema-layer invariant: ProcessBaselineAnomaly.mitre_technique is
Literal["T1036.005"] and cannot be overridden.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HuntEvilBaseline(BaseModel):
    """Expected baseline characteristics for a canonical Windows process.

    Loaded from `verdict/knowledge/hunt_evil.yml` at case_init and compared
    against `vol3.windows.pslist` + `vol3.windows.pstree` output.

    The 8 canonical processes: svchost, lsass, csrss, winlogon, services,
    wininit, explorer, smss.
    """

    model_config = ConfigDict(frozen=True)

    process_name: str
    expected_parent: str
    expected_path: str
    expected_signing: bool | None = None
    expected_instance_count: str | None = None
    notes: str | None = None
    schema_version: Literal["v1"] = "v1"


class ProcessBaselineAnomaly(BaseModel):
    """A Hypothesis subtype emitted when a process deviates from its baseline.

    Always maps to T1036.005 (Masquerading: Match Legitimate Name or Location).
    The `mitre_technique` field is locked to "T1036.005" — any other value
    causes a ValidationError.

    Captures what was observed vs what was expected so the LLM planner has
    structured context rather than free-form text.
    """

    model_config = ConfigDict(frozen=True)

    process_name: str
    observed_parent: str
    expected_parent: str
    observed_path: str
    expected_path: str
    deviation_description: str
    mitre_technique: Literal["T1036.005"] = "T1036.005"
    schema_version: Literal["v1"] = "v1"

    @field_validator("mitre_technique")
    @classmethod
    def _technique_must_be_T1036_005(cls, v: str) -> str:
        if v != "T1036.005":
            raise ValueError(
                f"ProcessBaselineAnomaly.mitre_technique must be 'T1036.005' "
                f"(Masquerading: Match Legitimate Name or Location); got {v!r}"
            )
        return v
