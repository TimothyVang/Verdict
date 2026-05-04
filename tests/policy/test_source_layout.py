from pathlib import Path


def test_application_source_uses_src_layout() -> None:
    assert Path("src/verdict/__init__.py").is_file()
    assert not Path("verdict/__init__.py").exists()
