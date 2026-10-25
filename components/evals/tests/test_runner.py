import csv
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from evals import AgentClient, load_golden, run_all, select_cases, summarize, write_outputs
from evals.run_evals import main
from evals.runner import SUMMARY_COLUMNS, CaseResult
from evals.scorers.judge import GatewayJudge, JudgeScore

CASES = load_golden()


class FakeJudge:
    def __init__(self, score: float = 0.75) -> None:
        self.score = score
        self.calls: list[str] = []

    def grade(self, metric: str, **kwargs: Any) -> JudgeScore:
        self.calls.append(metric)
        return JudgeScore(self.score, f"{metric} ok")


def fake_agent(tools: list[str] | None = None, cost: float = 0.001) -> AgentClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/documents/"):
            return httpx.Response(200, json={"body": "document text"})
        body = json.loads(request.content)
        tier = body["tier_override"]
        used = tools if tools is not None else ["search_policy"]
        return httpx.Response(
            200,
            json={
                "answer": "You have 30 days to report the incident within the terms. [1]",
                "citations": [{"doc_id": "ph-overview"}],
                "pending_approvals": [],
                "usage": {
                    "route": {"deployment": f"{tier}-a"},
                    "input_tokens": 1000,
                    "output_tokens": 100,
                    "cost_usd": cost,
                    "latency_ms": 900 if tier == "small" else 2500,
                    "tool_calls": used,
                    "fallback_used": False,
                },
            },
        )

    return AgentClient(
        "http://agent",
        client=httpx.Client(base_url="http://agent", transport=httpx.MockTransport(handler)),
    )


def test_sample_spreads_cases_over_the_languages() -> None:
    chosen = select_cases(CASES, ["en", "fil", "ceb", "id", "th", "ja"], 12)
    assert len(chosen) == 12
    assert {c.language for c in chosen} == {"en", "fil", "ceb", "id", "th", "ja"}
    assert [c.language for c in chosen[:6]] == ["en", "fil", "ceb", "id", "th", "ja"]
    assert len({c.case_type for c in chosen if c.language == "en"}) == 2


def test_sample_ten_over_six_languages_gives_each_at_least_one() -> None:
    chosen = select_cases(CASES, ["en", "fil", "ceb", "id", "th", "ja"], 10)
    assert len(chosen) == 10 and len({c.language for c in chosen}) == 6


def test_sample_is_deterministic_and_larger_samples_return_everything() -> None:
    languages = ["ja"]
    assert select_cases(CASES, languages, 5) == select_cases(CASES, languages, 5)
    assert len(select_cases(CASES, languages, None)) == 30
    assert len(select_cases(CASES, languages, 999)) == 30


def test_language_filter() -> None:
    assert {c.language for c in select_cases(CASES, ["th"], None)} == {"th"}


def test_a_run_scores_every_case_and_groups_by_language_and_model() -> None:
    cases = select_cases(CASES, ["en", "ja"], 6)
    judge = FakeJudge()
    results = run_all(cases, ["small", "large"], fake_agent(), judge, workers=2)
    assert len(results) == 12 and all(r.error is None for r in results)
    assert set(judge.calls) == {"groundedness", "relevance", "coherence"}
    rows = summarize(results)
    assert {(r["language"], r["model"]) for r in rows} == {
        ("en", "small"),
        ("en", "large"),
        ("ja", "small"),
        ("ja", "large"),
    }
    row = next(r for r in rows if r["language"] == "en" and r["model"] == "large")
    assert row["groundedness"] == 0.75 and row["p50_ms"] == 2500
    assert row["tokens_per_case"] == 1100 and row["cost_per_case_usd"] == pytest.approx(0.001)


def test_an_agent_error_is_recorded_and_excluded_from_the_scores() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "nope"})

    agent = AgentClient(
        "http://a",
        client=httpx.Client(base_url="http://a", transport=httpx.MockTransport(handler)),
    )
    results = run_all(select_cases(CASES, ["en"], 2), ["small"], agent, None)
    assert all(r.error and "422" in r.error for r in results)
    row = summarize(results)[0]
    assert row["errors"] == 2 and row["groundedness"] is None and row["cases"] == 2


def test_running_without_a_judge_leaves_the_model_graded_columns_empty(tmp_path: Path) -> None:
    results = run_all(select_cases(CASES, ["en"], 3), ["small"], fake_agent(), None)
    write_outputs(results, tmp_path)
    rows = list(csv.DictReader((tmp_path / "summary.csv").open()))
    assert rows[0]["groundedness"] == "" and rows[0]["tool_accuracy"] != ""


def test_summary_csv_has_one_row_per_language_and_model_and_the_required_columns(
    tmp_path: Path,
) -> None:
    cases = select_cases(CASES, ["en", "fil", "ceb", "id", "th", "ja"], 12)
    write_outputs(run_all(cases, ["small", "large"], fake_agent(), FakeJudge()), tmp_path)
    with (tmp_path / "summary.csv").open() as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == SUMMARY_COLUMNS
        rows = list(reader)
    assert len(rows) == 12
    assert len({(r["language"], r["model"]) for r in rows}) == 12
    assert (tmp_path / "cases-small.jsonl").exists() and (tmp_path / "cases-large.jsonl").exists()
    first = json.loads((tmp_path / "cases-small.jsonl").read_text().splitlines()[0])
    assert {"id", "answer", "scores", "tools_used", "cost_usd"} <= set(first)
    assert (tmp_path / "summary_detail.csv").exists()


def test_the_safety_rate_counts_adversarial_cases_when_there_are_some() -> None:
    adversarial = next(c for c in CASES if c.case_type == "adversarial")
    agent = fake_agent(tools=["draft_claim"])
    results = run_all([adversarial], ["small"], agent, None)
    assert summarize(results)[0]["safety_pass_rate"] == 0.0


def test_japanese_results_get_a_polite_form_score_and_others_do_not() -> None:
    ja = next(c for c in CASES if c.language == "ja")
    en = next(c for c in CASES if c.language == "en")
    results = run_all([ja, en], ["small"], fake_agent(), None)
    by_language = {r.language: r for r in results}
    assert by_language["ja"].scores["polite_form"] is not None
    assert by_language["en"].scores["polite_form"] is None


def test_the_gateway_judge_calls_the_chosen_tier_with_the_country_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        content = json.dumps({"score": 4, "reason": "fine"})
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "small-a",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            },
        )

    judge = GatewayJudge(
        "https://gw.azure-api.net/",
        {"ph": "key-ph"},
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    graded = judge.grade(
        "groundedness", country="ph", question="q", answer="a", context="c", reference="r"
    )
    assert graded.score == 0.75
    request = seen[0]
    assert request.url.path == "/small/chat/completions"
    assert request.headers["api-key"] == "key-ph" and request.headers["x-country"] == "ph"
    assert request.headers["x-app"] == "evals"
    with pytest.raises(ValueError, match="no gateway key"):
        judge.grade("coherence", country="th", question="", answer="", context="", reference="")


def test_the_cli_refuses_to_run_without_what_it_needs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-judge"]) == 2
    assert "agent-url" in capsys.readouterr().err
    assert main(["--agent-url", "http://a"]) == 2
    assert "judge needs" in capsys.readouterr().err
    assert main(["--agent-url", "http://a", "--no-judge", "--models", "huge"]) == 2
    assert main(["--agent-url", "http://a", "--no-judge", "--languages", "fr"]) == 2


def test_case_result_defaults_are_independent() -> None:
    a = CaseResult("a", "en", "ph", "faq", "small")
    b = CaseResult("b", "en", "ph", "faq", "small")
    a.tools_used.append("x")
    assert b.tools_used == []
