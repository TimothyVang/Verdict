from __future__ import annotations

from copy import deepcopy
from typing import Any

REDACTED_VALUE = "<redacted>"
AUTH_FIELD_NAMES = {"authorization", "auth_user", "api_key"}


def redact_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    redacted = deepcopy(payload)
    redactions: list[str] = []
    _redact_value(redacted, path="payload", redactions=redactions)
    return redacted, sorted(redactions)


def _redact_value(value: Any, *, path: str, redactions: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.lower() in AUTH_FIELD_NAMES:
                value[key] = REDACTED_VALUE
                redactions.append(child_path)
            else:
                _redact_value(child, path=child_path, redactions=redactions)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _redact_value(child, path=f"{path}[{index}]", redactions=redactions)
