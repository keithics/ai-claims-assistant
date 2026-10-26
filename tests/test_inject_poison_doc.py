import importlib.util
from pathlib import Path

from rag import IngestSettings

spec = importlib.util.spec_from_file_location(
    "inject_poison_doc", Path(__file__).resolve().parent.parent / "tools" / "inject_poison_doc.py"
)
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

SETTINGS = IngestSettings(
    search_endpoint="https://s",
    gateway_url="https://gw.azure-api.net",
    gateway_keys={"ph": "k"},
)


def test_the_poison_document_is_a_ph_document_with_injected_instructions() -> None:
    doc = tool.poison_document()
    assert doc.country == "ph" and doc.doc_id == "ph-poison-test"
    assert "draft_claim" in doc.body and "ignore all previous rules" in doc.body
    assert "30 days" in doc.body


def test_records_are_built_for_the_ph_index_and_embedded_with_the_ph_key() -> None:
    seen: list[str] = []

    def embed(texts, *, country):  # type: ignore[no-untyped-def]
        seen.append(country)
        return [[0.1, 0.2] for _ in texts]

    records = tool.poison_records(embed, SETTINGS)
    assert seen == ["ph"] and records
    assert all(r["country"] == "ph" and r["id"].startswith("ph-poison-test") for r in records)
    assert all(r["content_vector"] == [0.1, 0.2] for r in records)
    assert any("draft_claim" in r["content"] for r in records)
