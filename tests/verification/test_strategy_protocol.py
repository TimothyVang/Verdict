from __future__ import annotations

from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.strategy import (
    VerificationCandidate,
    VerificationResult,
    VerifierStrategy,
)
from verdict.verification.universal_self_consistency import UniversalSelfConsistency


class TwoOfThreeStrategy:
    def verify(self, candidates: list[VerificationCandidate]) -> VerificationResult:
        return UniversalSelfConsistency().verify(candidates)


def _candidate(
    *,
    artifact_paths: tuple[str, ...],
    mitre_technique: str,
    status: VerdictStatus,
) -> VerificationCandidate:
    return VerificationCandidate(
        source="verifier",
        artifact_paths=artifact_paths,
        mitre_technique=mitre_technique,
        status=status,
    )


def test_strategy_returns_verdict_result() -> None:
    strategy: VerifierStrategy = TwoOfThreeStrategy()
    result = strategy.verify(
        [
            _candidate(
                artifact_paths=("/case/a.json", "/case/b.json"),
                mitre_technique="T1059",
                status=VerdictStatus.VETTED_CLOUD,
            ),
            _candidate(
                artifact_paths=("/case/a.json", "/case/b.json"),
                mitre_technique="T1059",
                status=VerdictStatus.VETTED_CLOUD,
            ),
            _candidate(
                artifact_paths=("/case/c.json", "/case/d.json"),
                mitre_technique="T1106",
                status=VerdictStatus.CONTESTED,
            ),
        ],
    )

    assert result.status is VerdictStatus.VETTED_CLOUD
    assert result.agreement_count == 2


def test_universal_self_consistency_contests_without_majority() -> None:
    result = UniversalSelfConsistency().verify(
        [
            _candidate(
                artifact_paths=("/case/a.json", "/case/b.json"),
                mitre_technique="T1059",
                status=VerdictStatus.VETTED_CLOUD,
            ),
            _candidate(
                artifact_paths=("/case/c.json", "/case/d.json"),
                mitre_technique="T1059",
                status=VerdictStatus.VETTED_CLOUD,
            ),
            _candidate(
                artifact_paths=("/case/e.json", "/case/f.json"),
                mitre_technique="T1106",
                status=VerdictStatus.UNVERIFIABLE,
            ),
        ],
    )

    assert result.status is VerdictStatus.CONTESTED
    assert result.agreement_count == 1
