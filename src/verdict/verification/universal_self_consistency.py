from __future__ import annotations

import re
from collections import Counter, defaultdict

from pydantic import BaseModel

from verdict.schemas.finding import Finding
from verdict.schemas.verdict_status import VerdictStatus
from verdict.verification.strategy import VerificationCandidate, VerificationResult


class SelfConsistencyJudgement(BaseModel):
    status: VerdictStatus
    agreement_count: int
    selected_index: int | None
    findings: list[Finding]


class UniversalSelfConsistency:
    """Fallback verifier that accepts an existing 2-of-N agreement set."""

    def judge(self, findings: list[Finding]) -> SelfConsistencyJudgement:
        if not findings:
            return SelfConsistencyJudgement(
                status=VerdictStatus.UNVERIFIABLE,
                agreement_count=0,
                selected_index=None,
                findings=[],
            )

        best_pair: tuple[int, int] | None = None
        best_score = 0.0
        for left_index, left in enumerate(findings):
            for right_index, right in enumerate(findings[left_index + 1 :], start=left_index + 1):
                score = _finding_agreement_score(left, right)
                if score > best_score:
                    best_score = score
                    best_pair = (left_index, right_index)

        if best_pair is None or best_score < 0.50:
            return SelfConsistencyJudgement(
                status=VerdictStatus.CONTESTED,
                agreement_count=1,
                selected_index=0,
                findings=findings,
            )

        selected_index = best_pair[0]
        selected = findings[selected_index]
        return SelfConsistencyJudgement(
            status=selected.status,
            agreement_count=2,
            selected_index=selected_index,
            findings=[findings[index] for index in best_pair],
        )

    def verify(self, candidates: list[VerificationCandidate]) -> VerificationResult:
        grouped: dict[
            tuple[tuple[str, ...], str | None], list[VerificationCandidate]
        ] = defaultdict(list)
        for candidate in candidates:
            grouped[(candidate.artifact_paths, candidate.mitre_technique)].append(candidate)

        if not grouped:
            return VerificationResult(
                status=VerdictStatus.UNVERIFIABLE,
                agreement_count=0,
                candidates=[],
            )

        majority = max(grouped.values(), key=len)
        if len(majority) < 2:
            return VerificationResult(
                status=VerdictStatus.CONTESTED,
                agreement_count=len(majority),
                candidates=candidates,
            )

        statuses = Counter(candidate.status for candidate in majority)
        status, _count = statuses.most_common(1)[0]
        if status is VerdictStatus.CONTESTED:
            status = VerdictStatus.CONTESTED

        return VerificationResult(status=status, agreement_count=len(majority), candidates=majority)


def _finding_agreement_score(left: Finding, right: Finding) -> float:
    if left.mitre_technique != right.mitre_technique:
        return 0.0
    if set(left.artifact_paths) != set(right.artifact_paths):
        return 0.0
    return _jaccard(_tokens(left.rationale), _tokens(right.rationale))


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)
