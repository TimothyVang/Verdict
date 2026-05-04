from __future__ import annotations

from pathlib import Path

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.finding import Finding
from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.universal_self_consistency import UniversalSelfConsistency


def _finding(*, finding_id: str, rationale: str, mitre_technique: str = "T1014") -> Finding:
    return Finding(
        finding_id=finding_id,
        case_id="case-001",
        plan_id="plan-001",
        hypothesis_ids=["hyp-001"],
        artifact_paths=[Path("/case/psscan.json"), Path("/case/pslist.json")],
        artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
        caveats_acknowledged=[],
        mitre_technique=mitre_technique,
        evidence_hashes={
            Path("/case/psscan.json"): "a" * 64,
            Path("/case/pslist.json"): "b" * 64,
        },
        rationale=rationale,
        status=VerdictStatus.VETTED_AIRGAP,
    )


def test_judge_picks_most_consistent_rationale_among_n3() -> None:
    result = UniversalSelfConsistency().judge(
        [
            _finding(
                finding_id="finding-001",
                rationale=(
                    "psscan and pslist divergence is evidence consistent with hidden process DKOM"
                ),
            ),
            _finding(
                finding_id="finding-002",
                rationale=(
                    "hidden process DKOM is supported by pslist versus psscan divergence evidence"
                ),
            ),
            _finding(
                finding_id="finding-003",
                rationale="network beaconing suggests unrelated command and control activity",
                mitre_technique="T1071",
            ),
        ],
    )

    assert result.selected_index in {0, 1}
    assert result.status is not VerdictStatus.CONTESTED
    assert result.agreement_count == 2
