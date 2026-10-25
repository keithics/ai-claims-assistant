import re
from collections import defaultdict
from pathlib import Path

import pytest

from country_packs import load_country_packs
from rag import DocumentError, PolicyDocument, load_policy_documents, parse_document

COUNTRIES = ["id", "jp", "ph", "sg", "th"]
PACKS = load_country_packs()


@pytest.fixture(scope="module")
def documents() -> list[PolicyDocument]:
    return load_policy_documents(packs=PACKS)


def test_every_country_has_six_to_ten_documents(documents: list[PolicyDocument]) -> None:
    counts = {c: sum(1 for d in documents if d.country == c) for c in COUNTRIES}
    assert all(6 <= n <= 10 for n in counts.values()), counts


def test_every_document_has_valid_front_matter(documents: list[PolicyDocument]) -> None:
    for doc in documents:
        assert doc.country in PACKS
        assert doc.language in PACKS[doc.country].languages
        assert doc.title and doc.doc_id.startswith(f"{doc.country}-")
        assert doc.body.startswith("# ")


def test_documents_are_written_in_each_markets_language(documents: list[PolicyDocument]) -> None:
    languages = {c: {d.language for d in documents if d.country == c} for c in COUNTRIES}
    assert languages["jp"] == {"ja"}
    assert languages["th"] == {"th"}
    assert languages["id"] == {"id"}
    assert languages["sg"] == {"en"}
    assert languages["ph"] == {"en", "fil"}


def numbers(doc: PolicyDocument) -> tuple[str, ...]:
    return tuple(re.findall(r"\d[\d,.]*", doc.body.split("\n", 1)[1]))


def test_at_least_three_rules_differ_across_countries(documents: list[PolicyDocument]) -> None:
    by_topic: dict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for doc in documents:
        topic = doc.doc_id.removeprefix(f"{doc.country}-")
        if not topic.endswith("-fil"):
            by_topic[topic][doc.country] = numbers(doc)
    differing = [
        topic
        for topic, per_country in by_topic.items()
        if len(per_country) == len(COUNTRIES)
        and len(set(per_country.values())) == len(COUNTRIES)
        and all(per_country.values())
    ]
    assert len(differing) >= 3, differing
    assert {"deadlines", "motor", "health"} <= set(differing)


def test_exclusions_differ_per_country(documents: list[PolicyDocument]) -> None:
    bodies = {d.country: d.body for d in documents if d.doc_id.endswith("-exclusions")}
    assert len(set(bodies.values())) == len(COUNTRIES)


def write(tmp_path: Path, country: str, name: str, text: str) -> Path:
    folder = tmp_path / country
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


GOOD = "---\ncountry: ph\nlanguage: en\ntitle: T\ndoc_id: ph-x\n---\n\n# T\n\nBody\n"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# no front matter\n", "missing front matter"),
        (GOOD.replace("title: T\n", ""), "missing title"),
        (GOOD.replace("country: ph", "country: sg"), "does not match its folder"),
        (GOOD.replace("language: en", "language: ja"), "is not one of"),
        (GOOD.replace("doc_id: ph-x", "doc_id: ph-y"), "does not match the file name"),
        (GOOD.replace("# T\n\nBody\n", ""), "empty document body"),
        (GOOD.replace("title: T", "title: [unclosed"), "invalid front matter"),
    ],
)
def test_bad_documents_are_rejected(tmp_path: Path, text: str, expected: str) -> None:
    path = write(tmp_path, "ph", "ph-x", text)
    with pytest.raises(DocumentError, match=expected):
        parse_document(path, PACKS)


def test_duplicate_doc_ids_are_rejected(tmp_path: Path) -> None:
    write(tmp_path, "ph", "ph-x", GOOD)
    write(tmp_path, "sg", "ph-x", GOOD.replace("country: ph", "country: sg"))
    with pytest.raises(DocumentError, match="duplicate doc_id"):
        load_policy_documents(tmp_path, PACKS)


def test_policies_dir_can_be_overridden_for_container_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rag import default_policies_dir

    monkeypatch.setenv("RAG_POLICIES_DIR", str(tmp_path))
    assert default_policies_dir() == tmp_path
    write(tmp_path, "ph", "ph-x", GOOD)
    assert [d.doc_id for d in load_policy_documents(packs=PACKS)] == ["ph-x"]
