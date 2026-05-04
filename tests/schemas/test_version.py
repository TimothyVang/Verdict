from __future__ import annotations

from verdict.schemas.evidence import EvidenceManifest
from verdict.schemas.finding import Finding
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.plan import InvestigationPlan
from verdict.schemas.tool_output import ToolOutput
from verdict.schemas.version import SCHEMA_VERSION


def test_schema_version_is_1_on_all_top_level_models() -> None:
    for model in [InvestigationPlan, Finding, LedgerEntry, EvidenceManifest, ToolOutput]:
        assert model.model_fields["schema_version"].default == SCHEMA_VERSION == 1
