from __future__ import annotations

import verdict.tools as tools
from verdict.tools import external


def test_registered_forensic_tools_do_not_expose_host_execution_wrapper() -> None:
    assert not hasattr(external, "ExternalToolWrapper")
    assert "build_tool_wrapper" not in tools.__all__
