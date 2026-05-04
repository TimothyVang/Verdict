from __future__ import annotations

from pathlib import Path

from yaml import safe_load

from verdict.schemas.hunt_evil import HuntEvilBaseline


def test_eight_canonical_processes() -> None:
    data = safe_load(Path("src/verdict/knowledge/hunt_evil.yml").read_text())
    baselines = [HuntEvilBaseline.model_validate(item) for item in data["process_baselines"]]

    assert {baseline.process_name for baseline in baselines} == {
        "svchost.exe",
        "lsass.exe",
        "csrss.exe",
        "winlogon.exe",
        "services.exe",
        "wininit.exe",
        "explorer.exe",
        "smss.exe",
    }
