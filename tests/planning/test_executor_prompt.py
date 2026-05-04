from __future__ import annotations

from verdict.planning.executor_prompt import render_executor_prompt


def test_includes_caveats_and_hunt_evil() -> None:
    prompt = render_executor_prompt(role="memory")

    assert "AMCACHE_LASTMODIFIED_NOT_EXEC" in prompt
    assert "svchost.exe" in prompt
    assert "T1036.005" in prompt
