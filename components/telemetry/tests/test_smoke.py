import telemetry


def test_package_imports() -> None:
    assert telemetry.__all__ == []
