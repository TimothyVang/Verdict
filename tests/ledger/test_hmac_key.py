from __future__ import annotations

from pathlib import Path

import pytest

from verdict.ledger.hmac_key import load_or_create_hmac_key


def test_gpg_path_when_dev_tpmrm0_absent(tmp_path: Path) -> None:
    if Path("/dev/tpmrm0").exists():
        pytest.fail("Host has /dev/tpmrm0; run TPM-path coverage instead of fallback coverage")

    key_path = tmp_path / "key.gpg"
    gnupg_home = tmp_path / "gnupg"

    first = load_or_create_hmac_key(
        key_path=key_path,
        passphrase="verdict-test-passphrase",  # noqa: S106 - temporary test-only GPG secret.
        gnupg_home=gnupg_home,
    )
    second = load_or_create_hmac_key(
        key_path=key_path,
        passphrase="verdict-test-passphrase",  # noqa: S106 - temporary test-only GPG secret.
        gnupg_home=gnupg_home,
    )

    assert len(first) == 32
    assert first == second
    assert key_path.exists()
    assert key_path.read_bytes() != first
