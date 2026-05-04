from __future__ import annotations

from pydantic import BaseModel


class HuntEvilBaseline(BaseModel):
    """Canonical Windows process baseline entry from Hunt Evil doctrine."""

    process_name: str
    expected_parent_names: list[str]
    expected_path_prefixes: list[str]
    expected_user_names: list[str]


class ProcessBaselineAnomaly(BaseModel):
    """Observed deviation from a canonical Windows process baseline."""

    process_name: str
    observed_parent_name: str
    observed_path: str
    reason: str
    mitre_technique: str = "T1036.005"
