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


def test_finding_rejects_malformed_mitre_technique() -> None:
    with pytest.raises(ValidationError, match="mitre_technique"):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_bad_mitre_001"],
            artifact_paths=[Path("/case/artifacts/a.json"), Path("/case/artifacts/b.json")],
            artifact_classes=[ArtifactClass.PROCESS_MEMORY, ArtifactClass.YARA_HIT],
            mitre_technique="1055.012",
            evidence_hashes={Path("/case/artifacts/a.json"): "a" * 64},
            rationale="Malformed MITRE technique identifiers must not validate on findings.",
            status="VETTED_AIRGAP",
        )


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
        (ArtifactClass.USNJRNL, CaveatID.USNJRNL_WRAPS),
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


@pytest.mark.parametrize("logon_type", [3, 10])
def test_evtx_4624_type_3_or_10_requires_logon_caveat(logon_type: int) -> None:
    with pytest.raises(ValidationError, match=CaveatID.LOGON_TYPE_3_VS_10.value):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_logon_001"],
            artifact_paths=[Path("/case/artifacts/security.json"), Path("/case/artifacts/net.json")],
            artifact_classes=[ArtifactClass.EVTX_4624, ArtifactClass.NETWORK],
            caveats_acknowledged=[],
            mitre_technique="T1021.001",
            evtx_4624_logon_types=[logon_type],
            evidence_hashes={Path("/case/artifacts/security.json"): "a" * 64},
            rationale="Logon type 3 and 10 claims require explicit caveat acknowledgement.",
            status="VETTED_AIRGAP",
        )


def test_evtx_4624_other_logon_type_does_not_require_type_3_vs_10_caveat() -> None:
    finding = Finding(
        finding_id="finding-001",
        case_id="case-001",
        plan_id="plan-001",
        hypothesis_ids=["h_logon_001"],
        artifact_paths=[Path("/case/artifacts/security.json"), Path("/case/artifacts/net.json")],
        artifact_classes=[ArtifactClass.EVTX_4624, ArtifactClass.NETWORK],
        caveats_acknowledged=[],
        mitre_technique="T1021.001",
        evtx_4624_logon_types=[2],
        evidence_hashes={Path("/case/artifacts/security.json"): "a" * 64},
        rationale="Non-network and non-RDP 4624 logon types do not trigger the type 3 vs 10 caveat.",
        status="VETTED_AIRGAP",
    )

    assert finding.evtx_4624_logon_types == [2]


def test_evtx_4624_omitted_logon_type_requires_conservative_caveat() -> None:
    with pytest.raises(ValidationError, match=CaveatID.LOGON_TYPE_3_VS_10.value):
        Finding(
            finding_id="finding-001",
            case_id="case-001",
            plan_id="plan-001",
            hypothesis_ids=["h_logon_001"],
            artifact_paths=[Path("/case/artifacts/security.json"), Path("/case/artifacts/net.json")],
            artifact_classes=[ArtifactClass.EVTX_4624, ArtifactClass.NETWORK],
            caveats_acknowledged=[],
            mitre_technique="T1021.001",
            evidence_hashes={Path("/case/artifacts/security.json"): "a" * 64},
            rationale="Omitted 4624 logon type data must not bypass caveat enforcement.",
            status="VETTED_AIRGAP",
        )


def test_lolbin_finding_accepts_transcript_and_prefetch_corroboration() -> None:
    finding = Finding(
        finding_id="finding-lolbin-rundll32",
        case_id="case-001",
        plan_id="disk-lolbin-corroboration",
        hypothesis_ids=["h_lolbin_rundll32_transcript_prefetch"],
        artifact_paths=[
            Path("/case/artifacts/transcript.json"),
            Path("/case/artifacts/prefetch.json"),
        ],
        artifact_classes=[ArtifactClass.POWERSHELL_TRANSCRIPT, ArtifactClass.PREFETCH],
        caveats_acknowledged=[CaveatID.PREFETCH_SSD_DISABLED],
        mitre_technique="T1218.011",
        evidence_hashes={Path("/evidence/disk.E01"): "d" * 64},
        rationale="Evidence consistent with rundll32 LOLBin execution across transcript and Prefetch artifacts.",
        status="CONTESTED",
        contested_reasons=["local CLI parser finding requires verifier quorum before VETTED_CLOUD"],
    )

    assert finding.artifact_classes == [ArtifactClass.POWERSHELL_TRANSCRIPT, ArtifactClass.PREFETCH]
