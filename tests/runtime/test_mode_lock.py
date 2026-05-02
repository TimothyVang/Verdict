"""Tests for W3.C — Mode lock enforcement.

Covers:
  W3.C.1 — mode_at_case_init immutability + resume refusal on mode drift.
  W3.C.2 — verdict reverify produces parallel chain without mutating original.

No mocks of verdict.* internals (CLAUDE.md §3.10).
Patching of third-party sys.exit is acceptable per the boundary-patch rule.

The tests write real ledger files to a tmp_path fixture directory and exercise
the real mode-lock logic end-to-end.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import pytest

from verdict.cli.reverify import create_reverify_chain, derive_reverify_case_id
from verdict.runtime.case_store import read_case_init_mode, write_case_init_entry
from verdict.runtime.mode_lock import (
    ModeLockedError,
    assert_mode_lock,
    resume_mode_check_and_exit,
)
from verdict.schemas.ledger import LedgerEntry
from verdict.schemas.mode import Mode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case_init_entry(case_id: str, mode: Mode) -> LedgerEntry:
    """Build a minimal valid case_init LedgerEntry for test fixtures."""
    return LedgerEntry(
        entry_id="01TESTULID000000000",
        case_id=case_id,
        event_type="case_init",
        timestamp_utc=datetime.datetime(2026, 5, 2, 12, 0, 0, tzinfo=datetime.UTC),
        mode_at_case_init=mode,
        langfuse_session_id=case_id,
        langgraph_thread_id=case_id,
    )


# ---------------------------------------------------------------------------
# W3.C.1.a — Failing tests (RED gate)
# These tests MUST pass after W3.C.1.b lands (GREEN).
# ---------------------------------------------------------------------------


class TestModeLockError:
    """ModeLockedError carries the canonical message format from CLAUDE.md §3.4."""

    def test_error_message_format(self) -> None:
        """ModeLockedError.__str__ matches the exact CLAUDE.md §3.4 template."""
        err = ModeLockedError(
            case_id="case-abc123",
            original_mode=Mode.CLOUD,
            detected_mode=Mode.AIRGAP,
        )
        msg = str(err)
        assert "Case case-abc123" in msg
        assert "initialized in mode=cloud" in msg
        assert "current environment is mode=airgap" in msg
        assert "verdict reverify case-abc123 --mode airgap" in msg

    def test_error_is_runtime_error(self) -> None:
        """ModeLockedError is a RuntimeError subclass."""
        err = ModeLockedError("x", Mode.DUAL, Mode.CLOUD)
        assert isinstance(err, RuntimeError)

    def test_error_attributes(self) -> None:
        """ModeLockedError exposes case_id, original_mode, detected_mode."""
        err = ModeLockedError("my-case", Mode.AIRGAP, Mode.DUAL)
        assert err.case_id == "my-case"
        assert err.original_mode == Mode.AIRGAP
        assert err.detected_mode == Mode.DUAL


class TestAssertModeLock:
    """assert_mode_lock() raises ModeLockedError on drift; silent on match."""

    def test_same_mode_does_not_raise(self) -> None:
        for mode in Mode:
            assert_mode_lock("case1", mode, mode)  # must not raise

    def test_cloud_to_airgap_raises(self) -> None:
        with pytest.raises(ModeLockedError) as exc_info:
            assert_mode_lock("case2", Mode.CLOUD, Mode.AIRGAP)
        err = exc_info.value
        assert err.original_mode == Mode.CLOUD
        assert err.detected_mode == Mode.AIRGAP
        assert err.case_id == "case2"

    def test_airgap_to_dual_raises(self) -> None:
        with pytest.raises(ModeLockedError):
            assert_mode_lock("case3", Mode.AIRGAP, Mode.DUAL)

    def test_dual_to_cloud_raises(self) -> None:
        with pytest.raises(ModeLockedError):
            assert_mode_lock("case4", Mode.DUAL, Mode.CLOUD)

    def test_all_cross_mode_pairs_raise(self) -> None:
        """Every distinct pair of modes raises ModeLockedError."""
        modes = list(Mode)
        for orig in modes:
            for curr in modes:
                if orig != curr:
                    with pytest.raises(ModeLockedError):
                        assert_mode_lock("pair-test", orig, curr)


class TestResumeModeCheckAndExit:
    """resume_mode_check_and_exit() writes to stderr and exits(2) on drift."""

    def test_mismatch_exits_with_code_2(self, capsys) -> None:
        """On mode mismatch, the process exits with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            resume_mode_check_and_exit("case-x", Mode.CLOUD, Mode.AIRGAP)
        assert exc_info.value.code == 2

    def test_mismatch_writes_canonical_message_to_stderr(self, capsys) -> None:
        """Canonical error message is written to stderr on mismatch."""
        with pytest.raises(SystemExit):
            resume_mode_check_and_exit("case-y", Mode.CLOUD, Mode.DUAL)
        captured = capsys.readouterr()
        assert "Case case-y" in captured.err
        assert "initialized in mode=cloud" in captured.err
        assert "current environment is mode=dual" in captured.err
        assert "verdict reverify case-y --mode dual" in captured.err

    def test_matching_mode_does_not_exit(self) -> None:
        """On mode match, resume_mode_check_and_exit returns normally."""
        # Must not raise SystemExit.
        resume_mode_check_and_exit("case-z", Mode.CLOUD, Mode.CLOUD)


class TestModeLockEnforcedOnResume:
    """Integration: ledger write → read back → mode-lock check."""

    def test_resume_with_same_mode_succeeds(self, tmp_path: Path) -> None:
        """Writing cloud case_init then reading it back returns Mode.CLOUD."""
        case_id = "test-resume-same"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(case_id, Mode.CLOUD)
            write_case_init_entry(entry)

            read_back = read_case_init_mode(case_id)
            assert read_back == Mode.CLOUD

            # Should not raise.
            assert_mode_lock(case_id, read_back, Mode.CLOUD)
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_resume_with_different_mode_refuses(self, tmp_path: Path) -> None:
        """Reading a cloud case_init then checking against airgap raises ModeLockedError.

        This is the primary acceptance gate for W3.C.1.
        """
        case_id = "test-resume-drift"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(case_id, Mode.CLOUD)
            write_case_init_entry(entry)

            original_mode = read_case_init_mode(case_id)
            assert original_mode == Mode.CLOUD

            with pytest.raises(ModeLockedError) as exc_info:
                assert_mode_lock(case_id, original_mode, Mode.AIRGAP)

            err = exc_info.value
            assert err.case_id == case_id
            assert err.original_mode == Mode.CLOUD
            assert err.detected_mode == Mode.AIRGAP
            assert "verdict reverify" in str(err)
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_mode_at_case_init_immutable_across_entries(self, tmp_path: Path) -> None:
        """The mode read back from the ledger is identical to what was written.

        This verifies that ``mode_at_case_init`` survives the JSON round-trip
        without mutation — the JSON serialisation / deserialisation path
        must preserve the Mode enum value.
        """
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            for mode in Mode:
                case_id = f"test-immutable-{mode.value}"
                entry = _make_case_init_entry(case_id, mode)
                write_case_init_entry(entry)

                read_back = read_case_init_mode(case_id)
                assert read_back == mode, (
                    f"Expected mode_at_case_init={mode!r} to survive round-trip, "
                    f"got {read_back!r}"
                )
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_missing_ledger_raises_file_not_found(self, tmp_path: Path) -> None:
        """read_case_init_mode raises FileNotFoundError for unknown case IDs."""
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            with pytest.raises(FileNotFoundError):
                read_case_init_mode("does-not-exist")
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_ledger_without_case_init_raises_value_error(self, tmp_path: Path) -> None:
        """read_case_init_mode raises ValueError if no case_init entry is found."""
        case_id = "no-case-init"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            # Write a non-case_init entry directly.
            case_dir = tmp_path / case_id
            case_dir.mkdir(parents=True)
            ledger_file = case_dir / "ledger.jsonl"
            # A tool_call entry has no case_init.
            raw = {
                "entry_id": "01OTHER",
                "case_id": case_id,
                "event_type": "tool_call",
                "timestamp_utc": "2026-05-02T12:00:00+00:00",
                "mode_at_case_init": "cloud",
                "payload": {},
                "prev_entry_hash": "",
                "hmac_sig": "",
            }
            ledger_file.write_text(json.dumps(raw) + "\n", encoding="utf-8")

            with pytest.raises(ValueError, match="No 'case_init' entry found"):
                read_case_init_mode(case_id)
        finally:
            del os.environ["VERDICT_CASES_DIR"]


# ---------------------------------------------------------------------------
# W3.C.2.a — Failing tests for reverify command (RED gate)
# These tests MUST pass after W3.C.2.b lands (GREEN).
# ---------------------------------------------------------------------------


class TestReverifyCaseIdDerivation:
    """derive_reverify_case_id() produces the expected suffixed ID."""

    def test_cloud_suffix(self) -> None:
        assert derive_reverify_case_id("ABC123", Mode.CLOUD) == "ABC123.reverify-cloud"

    def test_airgap_suffix(self) -> None:
        assert derive_reverify_case_id("ABC123", Mode.AIRGAP) == "ABC123.reverify-airgap"

    def test_dual_suffix(self) -> None:
        assert derive_reverify_case_id("ABC123", Mode.DUAL) == "ABC123.reverify-dual"

    def test_preserves_original_id(self) -> None:
        original = "01HX3Y4Z5A6B7C8D"
        for mode in Mode:
            derived = derive_reverify_case_id(original, mode)
            assert derived.startswith(original + ".")


class TestCreateReverifyChain:
    """create_reverify_chain() creates a parallel chain without mutating original."""

    def test_reverify_creates_new_case_id(self, tmp_path: Path) -> None:
        """Reverify returns the derived case ID."""
        original_id = "orig-001"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            # Seed original case.
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            new_id = create_reverify_chain(original_id, Mode.DUAL)
            assert new_id == f"{original_id}.reverify-dual"
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_does_not_mutate_original(self, tmp_path: Path) -> None:
        """The original case's ledger is untouched after reverify.

        This is the primary acceptance gate for W3.C.2.
        """
        original_id = "orig-002"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            # Record original ledger contents.
            original_ledger_path = tmp_path / original_id / "ledger.jsonl"
            original_contents_before = original_ledger_path.read_text(encoding="utf-8")

            # Run reverify.
            create_reverify_chain(original_id, Mode.DUAL)

            # Original ledger must be byte-for-byte identical.
            original_contents_after = original_ledger_path.read_text(encoding="utf-8")
            assert original_contents_before == original_contents_after, (
                "Original ledger was mutated by create_reverify_chain()"
            )
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_creates_new_ledger_with_correct_mode(self, tmp_path: Path) -> None:
        """The new chain's ledger has a case_init entry with the requested mode."""
        original_id = "orig-003"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            new_id = create_reverify_chain(original_id, Mode.DUAL)

            new_mode = read_case_init_mode(new_id)
            assert new_mode == Mode.DUAL
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_new_chain_records_original_reference(self, tmp_path: Path) -> None:
        """The new chain's case_init payload records which case it re-verifies."""
        original_id = "orig-004"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            new_id = create_reverify_chain(original_id, Mode.AIRGAP)

            # Read raw ledger to check payload.
            new_ledger = tmp_path / new_id / "ledger.jsonl"
            raw = json.loads(new_ledger.read_text(encoding="utf-8").strip())
            assert raw["payload"]["reverify_of"] == original_id
            assert raw["payload"]["reverify_mode"] == "airgap"
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_raises_if_original_missing(self, tmp_path: Path) -> None:
        """create_reverify_chain raises FileNotFoundError for non-existent original."""
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            with pytest.raises(FileNotFoundError):
                create_reverify_chain("ghost-case", Mode.DUAL)
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_raises_if_chain_already_exists(self, tmp_path: Path) -> None:
        """Second reverify call for same (original, mode) raises FileExistsError."""
        original_id = "orig-005"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            create_reverify_chain(original_id, Mode.DUAL)

            with pytest.raises(FileExistsError):
                create_reverify_chain(original_id, Mode.DUAL)
        finally:
            del os.environ["VERDICT_CASES_DIR"]

    def test_reverify_original_mode_unchanged_after_new_chain(self, tmp_path: Path) -> None:
        """The original case's mode_at_case_init is unchanged after reverify."""
        original_id = "orig-006"
        os.environ["VERDICT_CASES_DIR"] = str(tmp_path)
        try:
            entry = _make_case_init_entry(original_id, Mode.CLOUD)
            write_case_init_entry(entry)

            original_mode_before = read_case_init_mode(original_id)

            create_reverify_chain(original_id, Mode.DUAL)

            original_mode_after = read_case_init_mode(original_id)
            assert original_mode_before == original_mode_after == Mode.CLOUD
        finally:
            del os.environ["VERDICT_CASES_DIR"]
