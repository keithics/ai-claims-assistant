import json
from pathlib import Path

import pytest

from country_packs import load_country_packs
from evals.golden import (
    CASE_TYPES,
    LANGUAGES,
    GoldenCase,
    GoldenError,
    load_golden,
)

CASES = load_golden()


def good(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "en-faq-01",
        "language": "en",
        "country": "ph",
        "input": "How do I file a claim?",
        "expected_answer": "Report within 30 days.",
        "expected_source": "ph-overview",
        "expected_tool": "search_policy",
        "risk": "low",
        "case_type": "faq",
        "reviewed_by_native": False,
    }
    return {**base, **overrides}


def test_there_are_180_cases_30_per_language_and_30_per_type() -> None:
    assert len(CASES) == 180
    for language in LANGUAGES:
        assert sum(c.language == language for c in CASES) == 30
    for case_type in CASE_TYPES:
        assert sum(c.case_type == case_type for c in CASES) == 30


def test_each_language_has_five_of_each_type() -> None:
    for language in LANGUAGES:
        for case_type in CASE_TYPES:
            matching = [c for c in CASES if c.language == language and c.case_type == case_type]
            assert len(matching) == 5, (language, case_type)


def test_no_case_claims_to_be_native_reviewed_yet() -> None:
    assert not any(c.reviewed_by_native for c in CASES)


def test_ids_are_unique() -> None:
    assert len({c.id for c in CASES}) == 180


def test_every_case_uses_a_language_its_country_supports() -> None:
    packs = load_country_packs()
    bad = [c.id for c in CASES if c.language not in packs[c.country].languages]
    assert bad == []


def test_adversarial_and_filing_cases_are_high_risk_except_prompt_probes() -> None:
    for case in CASES:
        if case.case_type == "claim_filing":
            assert case.risk == "high"
    assert sum(c.risk == "high" for c in CASES if c.case_type == "adversarial") >= 4 * 6


def test_japanese_has_casual_inputs_that_must_be_answered_politely() -> None:
    ja = [c for c in CASES if c.language == "ja"]
    assert any("丁寧" in c.expected_answer for c in ja)


def test_code_switch_cases_mix_scripts_or_languages() -> None:
    ja = [c for c in CASES if c.language == "ja" and c.case_type == "code_switch"]
    assert all(any(ch.isascii() and ch.isalpha() for ch in c.input) for c in ja)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"language": "fr"}, "language"),
        ({"case_type": "chitchat"}, "case_type"),
        ({"risk": "medium"}, "risk"),
        ({"id": "en-claim-status-01"}, "does not match"),
        ({"expected_tool": "none"}, "search_policy"),
        ({"expected_source": None}, "search_policy"),
        ({"expected_source": "xx-doc"}, "policy doc id"),
        ({"surprise": 1}, "surprise"),
        ({"country": "philippines"}, "country"),
        ({"input": ""}, "input"),
    ],
)
def test_schema_rejects_bad_cases(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GoldenCase.model_validate(good(**overrides))


def test_filing_cases_must_expect_a_draft_and_high_risk() -> None:
    with pytest.raises(ValueError, match="draft_claim"):
        GoldenCase.model_validate(
            good(id="en-claim-filing-01", case_type="claim_filing", expected_source=None)
        )


def test_status_and_adversarial_tool_rules() -> None:
    with pytest.raises(ValueError, match="get_claim_status"):
        GoldenCase.model_validate(
            good(id="en-claim-status-01", case_type="claim_status", expected_source=None)
        )
    with pytest.raises(ValueError, match="no tool"):
        GoldenCase.model_validate(
            good(id="en-adversarial-01", case_type="adversarial", expected_source=None)
        )


def test_loader_names_the_line_of_a_bad_case(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    path.write_text(json.dumps(good()) + "\n" + json.dumps(good(language="fr")) + "\n")
    with pytest.raises(GoldenError, match=r"g\.jsonl line 2"):
        load_golden(path)


def test_loader_rejects_malformed_json_and_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    path.write_text("{not json}\n")
    with pytest.raises(GoldenError, match="line 1"):
        load_golden(path)
    path.write_text(json.dumps(good()) + "\n\n" + json.dumps(good()) + "\n")
    with pytest.raises(GoldenError, match="duplicate case ids: en-faq-01"):
        load_golden(path)
