import httpx


def test_boundary_patch_symbol_is_allowed() -> None:
    assert httpx.Client is not None
