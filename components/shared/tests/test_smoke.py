import shared


def test_package_imports() -> None:
    assert "cost_usd" in shared.__all__
