from __future__ import annotations

import sys
from pathlib import Path

from verdict.tools.external import ExternalToolSpec, ExternalToolWrapper


def test_external_tool_wrapper_runs_real_process_and_hashes_output(tmp_path: Path) -> None:
    evidence = tmp_path / "sample.mem"
    evidence.write_text("evidence bytes", encoding="utf-8")
    script = tmp_path / "tool_script.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "path = Path(sys.argv[1])\n"
        "print(f'evidence={path.name} size={path.stat().st_size}')\n",
        encoding="utf-8",
    )

    wrapper = ExternalToolWrapper(
        ExternalToolSpec(
            tool_name="test.real_process",
            executable_candidates=(sys.executable,),
            base_args=(str(script), str(evidence)),
            artifact_type="process_output",
            version_args=("--version",),
        ),
        evidence_path=evidence,
    )

    output = wrapper.execute_for_evidence(evidence_hash="a" * 64)

    assert output.exit_code == 0
    assert output.parsed_artifacts == []
    assert output.parse_warnings == [
        "raw external output captured; no per-tool parser has claimed artifacts"
    ]
