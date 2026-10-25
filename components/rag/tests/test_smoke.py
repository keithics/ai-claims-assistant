import rag


def test_package_imports() -> None:
    assert "load_policy_documents" in rag.__all__
