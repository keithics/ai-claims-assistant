import json
from pathlib import Path

import pytest
import yaml

from evals.propose import (
    DEFAULT_GATE,
    case_passes,
    cells,
    load_gate,
    load_results,
    propose,
    render_yaml,
)
from evals.propose_routing import CURRENT, main
from router import parse_routing_config

GATE = load_gate()
CURRENT_CFG = parse_routing_config(CURRENT.read_text())


def result(language: str, case_type: str, ok: bool = True, **scores: float | None) -> dict:
    base = {
        "groundedness": 1.0 if ok else 0.25,
        "relevance": 1.0 if ok else 0.25,
        "language_fit": 1.0,
        "tool_accuracy": 1.0,
        "safety_pass": 1.0,
        "polite_form": None,
    }
    return {
        "id": f"{language}-{case_type}",
        "language": language,
        "case_type": case_type,
        "error": None,
        "scores": {**base, **scores},
    }


def test_the_gate_file_loads() -> None:
    assert DEFAULT_GATE.exists() and GATE.routing.min_cases_per_cell >= 1


@pytest.mark.parametrize(
    ("overrides", "passes"),
    [
        ({}, True),
        ({"groundedness": 0.5}, False),
        ({"relevance": 0.5}, False),
        ({"language_fit": 0.0}, False),
        ({"tool_accuracy": 0.0}, False),
        ({"safety_pass": 0.0}, False),
        ({"polite_form": 0.5}, False),
        ({"polite_form": 1.0}, True),
        ({"groundedness": None}, False),
    ],
)
def test_a_case_passes_only_when_every_bar_is_met(
    overrides: dict[str, float | None], passes: bool
) -> None:
    assert case_passes(result("en", "faq", **overrides), GATE.case_passes) is passes


def test_cells_group_by_language_and_intent_and_skip_errors_and_unrouted_types() -> None:
    results = [
        result("en", "faq"),
        result("en", "faq", ok=False),
        result("en", "code_switch"),
        result("en", "adversarial"),
        result("en", "claim_filing"),
        {**result("en", "faq"), "error": "boom"},
    ]
    found = {(c.language, c.intent): (c.cases, c.passed) for c in cells(results, GATE.case_passes)}
    assert found == {("en", "faq"): (2, 1), ("en", "country_rule"): (1, 1)}


def many(language: str, case_type: str, passed: int, total: int) -> list[dict]:
    return [result(language, case_type, ok=i < passed) for i in range(total)]


def test_small_stays_where_it_meets_the_bar_and_large_is_proposed_elsewhere() -> None:
    results = (
        many("en", "faq", 5, 5)
        + many("en", "country_rule", 5, 5)
        + many("en", "claim_status", 5, 5)
        + many("ceb", "faq", 2, 5)
        + many("ceb", "country_rule", 5, 5)
        + many("ceb", "claim_status", 5, 5)
    )
    proposed, notes = propose(CURRENT_CFG, results, GATE)
    assert [(r.language, r.intent, r.tier) for r in proposed.rules] == [("ceb", "faq", "large")]
    assert proposed.version == CURRENT_CFG.version + 1
    assert proposed.default_tier == "small"
    assert any("ceb/faq: small passed 2/5, use large" in n for n in notes)
    assert any("en/faq: small passed 5/5" in n for n in notes)


def test_a_cell_with_too_little_data_is_kept_on_large() -> None:
    results = many("en", "faq", 2, 2)
    proposed, notes = propose(CURRENT_CFG, results, GATE)
    assert ("en", "faq", "large") in [(r.language, r.intent, r.tier) for r in proposed.rules]
    assert any("not enough data" in n for n in notes)


def test_the_proposal_keeps_deployments_and_output_limits() -> None:
    proposed, _ = propose(CURRENT_CFG, many("en", "faq", 5, 5), GATE)
    assert proposed.deployments == CURRENT_CFG.deployments
    assert proposed.output_limits == CURRENT_CFG.output_limits


def test_the_rendered_yaml_round_trips_and_names_its_evidence() -> None:
    results = many("en", "faq", 5, 5) + many("ceb", "faq", 1, 5)
    proposed, notes = propose(CURRENT_CFG, results, GATE)
    text = render_yaml(proposed, notes)
    assert text.startswith("# PROPOSED routing")
    assert "ceb/faq: small passed 1/5" in text
    assert parse_routing_config(text) == proposed
    assert yaml.safe_load(text)["version"] == proposed.version


def test_the_cli_writes_the_proposal_and_refuses_without_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--results", str(tmp_path)]) == 2
    assert "run-evals" in capsys.readouterr().err
    (tmp_path / "cases-small.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in many("en", "faq", 5, 5))
    )
    assert main(["--results", str(tmp_path)]) == 0
    assert (tmp_path / "routing.proposed.yaml").exists()
    assert load_results(tmp_path / "cases-small.jsonl")[0]["language"] == "en"
    assert main(["--results", str(tmp_path), "--current", str(tmp_path / "nope.yaml")]) == 2
