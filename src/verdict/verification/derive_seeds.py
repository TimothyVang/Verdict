from __future__ import annotations

from blake3 import blake3

_SEED_DERIVATION_KEY = b"VERDICT self-consistency seeds\0\0"


def derive_seeds(case_id: str) -> tuple[int, int, int]:
    digest = blake3(case_id.encode(), key=_SEED_DERIVATION_KEY).digest(length=12)
    return tuple(int.from_bytes(digest[index : index + 4], "big") for index in range(0, 12, 4))
