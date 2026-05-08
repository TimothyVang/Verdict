from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_env_example_documents_runtime_blocker_variables() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    for variable in (
        "ANTHROPIC_API_KEY=",
        "CLAUDE_CODE_OAUTH_TOKEN=",
        "OPENROUTER_API_KEY=",
        "SGLANG_BASE_URL=",
        "SGLANG_GLM_BASE_URL=",
        "VERDICT_HMAC_KEY_HEX=",
        "VERDICT_HMAC_PASSPHRASE=",
        "VERDICT_MICROSANDBOX_IMAGE=",
        "LANGFUSE_HOST=",
    ):
        assert variable in env_example


def test_env_example_uses_current_microsandbox_image_variable() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "VERDICT_MICROSANDBOX_IMAGE=" in env_example
    assert "MICROSANDBOX_ROOTFS_PATH=" not in env_example
    assert "MICROSANDBOX_ROOTFS_SHA256=" not in env_example


def test_readme_quickstart_uses_install_script() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "bash scripts/install.sh" in readme
