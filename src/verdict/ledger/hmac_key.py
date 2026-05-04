from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import which


def load_or_create_hmac_key(*, key_path: Path, passphrase: str, gnupg_home: Path) -> bytes:
    if Path("/dev/tpmrm0").exists():
        raise RuntimeError("TPM-backed HMAC key path is not implemented on this host yet")

    if key_path.exists():
        return _decrypt_key(key_path=key_path, passphrase=passphrase, gnupg_home=gnupg_home)

    key = os.urandom(32)
    _encrypt_key(key=key, key_path=key_path, passphrase=passphrase, gnupg_home=gnupg_home)
    return key


def _gpg_binary() -> str:
    gpg = which("gpg")
    if gpg is None:
        raise RuntimeError("gpg is required for encrypted HMAC key fallback")
    return gpg


def _gpg_env(gnupg_home: Path) -> dict[str, str]:
    gnupg_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GNUPGHOME"] = str(gnupg_home)
    return env


def _encrypt_key(*, key: bytes, key_path: Path, passphrase: str, gnupg_home: Path) -> None:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603 - gpg path is resolved with shutil.which.
        [
            _gpg_binary(),
            "--batch",
            "--yes",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            passphrase,
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--output",
            str(key_path),
        ],
        input=key,
        check=True,
        env=_gpg_env(gnupg_home),
    )


def _decrypt_key(*, key_path: Path, passphrase: str, gnupg_home: Path) -> bytes:
    result = subprocess.run(  # noqa: S603 - gpg path is resolved with shutil.which.
        [
            _gpg_binary(),
            "--batch",
            "--yes",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            passphrase,
            "--decrypt",
            str(key_path),
        ],
        check=True,
        capture_output=True,
        env=_gpg_env(gnupg_home),
    )
    if len(result.stdout) != 32:
        raise RuntimeError("decrypted HMAC key has invalid length")
    return result.stdout
