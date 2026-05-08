from __future__ import annotations

import os
import urllib.error
import urllib.request
from enum import StrEnum

from verdict.planning.planner import CloudPlanner, LocalPlanner, Planner


class Mode(StrEnum):
    """Operational mode detected at case initialization and locked thereafter."""

    CLOUD = "CLOUD"
    AIRGAP = "AIRGAP"
    DUAL = "DUAL"


class ModeDetectionError(RuntimeError):
    """Raised when no usable VERDICT operating mode is configured."""


def bind_planner_at_gateway_init(mode: Mode) -> Planner:
    if mode is Mode.AIRGAP:
        return LocalPlanner()
    return CloudPlanner()


def detect_mode(*, timeout_seconds: float = 2.0) -> Mode:
    """Detect the best available mode from host-side credentials and local inference config."""
    cloud_available = has_cloud_credential()
    local_available = has_local_inference_endpoint(timeout_seconds=timeout_seconds)

    if cloud_available and local_available:
        return Mode.DUAL
    if local_available:
        return Mode.AIRGAP
    if cloud_available:
        return Mode.CLOUD
    raise ModeDetectionError(
        "no VERDICT mode is configured; set ANTHROPIC_API_KEY, "
        "CLAUDE_CODE_OAUTH_TOKEN, or SGLANG_BASE_URL"
    )


def has_cloud_credential() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        or os.environ.get("OPENROUTER_API_KEY")
    )


def has_local_inference_endpoint(*, timeout_seconds: float = 2.0) -> bool:
    base_url = os.environ.get("SGLANG_BASE_URL")
    if not base_url:
        return False
    try:
        url = base_url.rstrip("/") + "/v1/models"
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


def mode_is_available(mode: Mode, *, timeout_seconds: float = 2.0) -> bool:
    if mode is Mode.CLOUD:
        return has_cloud_credential()
    if mode is Mode.AIRGAP:
        return has_local_inference_endpoint(timeout_seconds=timeout_seconds)
    if mode is Mode.DUAL:
        return has_cloud_credential() and has_local_inference_endpoint(
            timeout_seconds=timeout_seconds
        )
    return False


def parse_mode(value: str) -> Mode:
    normalized = value.replace("-", "_").upper()
    if normalized == "AIRGAP":
        return Mode.AIRGAP
    if normalized == "CLOUD":
        return Mode.CLOUD
    if normalized == "DUAL":
        return Mode.DUAL
    raise ValueError(f"unknown mode: {value}")
