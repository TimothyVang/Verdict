from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from verdict.runtime.mode_detect import (
    Mode,
    ModeDetectionError,
    detect_mode,
    has_cloud_credential,
    has_local_inference_endpoint,
)


class _ModelsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data": []}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def test_openrouter_counts_as_host_side_cloud_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "host-side-fallback")

    assert has_cloud_credential() is True


def test_local_inference_requires_reachable_sglang_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGLANG_BASE_URL", "http://127.0.0.1:1")

    assert has_local_inference_endpoint(timeout_seconds=0.1) is False


def test_detect_mode_returns_airgap_only_when_sglang_is_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    server = HTTPServer(("127.0.0.1", 0), _ModelsHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SGLANG_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        assert detect_mode() is Mode.AIRGAP
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_detect_mode_rejects_unreachable_sglang_without_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("SGLANG_BASE_URL", "http://127.0.0.1:1")

    with pytest.raises(ModeDetectionError):
        detect_mode(timeout_seconds=0.1)
