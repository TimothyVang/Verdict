from __future__ import annotations

from verdict.sandboxes.microsandbox_provider import microsandbox_status


def test_microsandbox_status_reports_boolean_availability() -> None:
    status = microsandbox_status()

    assert isinstance(status.available, bool)
    assert status.binary is None or status.binary
