from pathlib import Path


def test_policies_dir_exists() -> None:
    assert (Path(__file__).parent.parent / "policies").is_dir()
