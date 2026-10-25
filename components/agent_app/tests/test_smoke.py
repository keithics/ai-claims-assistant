import agent_app


def test_package_imports() -> None:
    assert "create_app" in agent_app.__all__
