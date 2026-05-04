from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from verdict.schemas.artifact_class import ArtifactClass
from verdict.schemas.caveat_id import CaveatID
from verdict.schemas.finding import Finding


def test_finding_round_trips_through_json() -> None:
    finding = Finding(
        finding_id="finding-001",
        case_id="case-001",
        plan_id="plan-001",
        hypothesis_ids=["h_proc_inject_001"],
        artifact_paths=[Path("/case/artifacts/psscan.json"), Path("/case/artifacts/malfind.json")],
        artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
        caveats_acknowledged=[CaveatID.SYSMON_PROCESSGUID_OVER_PID],
        mitre_technique="T1055.012",
        evidence_hashes={Path("/case/artifacts/psscan.json"): "a" * 64},
        rationale="Evidence consistent with process injection across memory artifacts.",
        status="VETTED_AIRGAP",
        contested_reasons=[],
    )

    restored = Finding.model_validate_json(finding.model_dump_json())

    assert restored == finding


def test_artifact_paths_min_length_2() -> None:
    with pytest.raises(ValidationError):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_proc_inject_001"],
            artifact_paths=[Path("/case/artifacts/psscan.json")],
            artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
            caveats_acknowledged=[],
            mitre_technique="T1055.012",
            evidence_hashes={Path("/case/artifacts/psscan.json"): "a" * 64},
            rationale="Single artifact paths are insufficient for execution claims.",
            status="VETTED_AIRGAP",
            contested_reasons=[],
        )


def test_artifact_classes_min_length_2() -> None:
    with pytest.raises(ValidationError):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_proc_inject_001"],
            artifact_paths=[
                Path("/case/artifacts/psscan.json"),
                Path("/case/artifacts/malfind.json"),
            ],
            artifact_classes=[ArtifactClass.PROCESS_MEMORY],
            caveats_acknowledged=[],
            mitre_technique="T1055.012",
            evidence_hashes={Path("/case/artifacts/psscan.json"): "a" * 64},
            rationale="Single artifact classes are insufficient for execution claims.",
            status="VETTED_AIRGAP",
            contested_reasons=[],
        )


def test_caveats_acknowledged_default_empty() -> None:
    finding = Finding(
        finding_id="finding-001",
        case_id="case-001",
        plan_id="plan-001",
        hypothesis_ids=["h_proc_inject_001"],
        artifact_paths=[Path("/case/artifacts/psscan.json"), Path("/case/artifacts/malfind.json")],
        artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
        mitre_technique="T1055.012",
        evidence_hashes={Path("/case/artifacts/psscan.json"): "a" * 64},
        rationale="Evidence consistent with process injection across memory artifacts.",
        status="VETTED_AIRGAP",
        contested_reasons=[],
    )

    assert finding.caveats_acknowledged == []


@pytest.mark.parametrize("mitre_technique", ["T1059", "T1106", "T1204", "T1218", "T1543", "T1547"])
def test_execution_claim_requires_two_classes(mitre_technique: str) -> None:
    with pytest.raises(ValidationError):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_exec_001"],
            artifact_paths=[Path("/case/artifacts/a.json"), Path("/case/artifacts/b.json")],
            artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.PROCESS_MEMORY],
            mitre_technique=mitre_technique,
            evidence_hashes={Path("/case/artifacts/a.json"): "a" * 64},
            rationale="Execution claims require two distinct artifact classes.",
            status="VETTED_AIRGAP",
        )


@pytest.mark.parametrize(
    ("artifact_class", "required_caveat"),
    [
        (ArtifactClass.AMCACHE, CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC),
        (ArtifactClass.SHIMCACHE, CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81),
        (ArtifactClass.PREFETCH, CaveatID.PREFETCH_SSD_DISABLED),
        (ArtifactClass.MFT, CaveatID.MFT_SI_STOMPABLE),
        (ArtifactClass.SYSMON_1, CaveatID.SYSMON_PROCESSGUID_OVER_PID),
    ],
)
def test_available_caveat_required_when_artifact_class_cited(
    artifact_class: ArtifactClass,
    required_caveat: CaveatID,
) -> None:
    with pytest.raises(ValidationError, match=required_caveat.value):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_caveat_001"],
            artifact_paths=[Path("/case/artifacts/a.json"), Path("/case/artifacts/b.json")],
            artifact_classes=[artifact_class, ArtifactClass.YARA_HIT],
            caveats_acknowledged=[],
            mitre_technique="T1014",
            evidence_hashes={Path("/case/artifacts/a.json"): "a" * 64},
            rationale="Cited caveat-triggering artifacts require explicit caveat acknowledgement.",
            status="VETTED_AIRGAP",
        )
