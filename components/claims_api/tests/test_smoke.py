import claims_api


def test_package_imports() -> None:
    assert "create_app" in claims_api.__all__
