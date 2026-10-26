import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from evals.harmful import (
    CATEGORIES,
    HarmfulCase,
    HarmfulResult,
    judge_case,
    load_harmful,
    run_harmful,
    summarize,
    write_outputs,
)
from evals.run_harmful import main
from evals.runner import AgentClient
from evals.scorers.judge import PROMPTS, JudgeScore

CASES = load_harmful()


class Judge:
    def __init__(self, score: float) -> None:
        self.score = score
        self.metrics: list[str] = []

    def grade(self, metric: str, **kwargs: Any) -> JudgeScore:
        self.metrics.append(metric)
        return JudgeScore(self.score, "")


def body(
    fired: list[str] | None = None, tools: list[str] | None = None, approvals: int = 0
) -> dict:
    return {
        "answer": "I cannot help with that.",
        "pending_approvals": [{}] * approvals,
        "usage": {"levers_fired": fired or [], "tool_calls": tools or []},
    }


def test_the_set_covers_every_language_and_category_twice() -> None:
    assert len(CASES) == 48
    for language in ("en", "fil", "ceb", "id", "th", "ja"):
        for category in CATEGORIES:
            matching = [c for c in CASES if c.language == language and c.category == category]
            assert len(matching) == 2, (language, category)


def test_cases_use_a_country_that_supports_their_language() -> None:
    from country_packs import load_country_packs

    packs = load_country_packs()
    assert all(c.language in packs[c.country].languages for c in CASES)
    assert not any(c.reviewed_by_native for c in CASES)
    assert len({c.id for c in CASES}) == 48


def test_a_request_the_content_filter_blocked_counts_as_caught_by_the_filter() -> None:
    result = judge_case(CASES[0], "small", body(["content_filter"]), Judge(0.0))
    assert result.passed and result.caught_by == "filter" and result.refusal_score is None


def test_a_clear_refusal_by_the_model_passes_and_a_weak_one_does_not() -> None:
    strong = judge_case(CASES[0], "small", body(), Judge(1.0))
    assert strong.passed and strong.caught_by == "model" and strong.refusal_score == 1.0
    weak = judge_case(CASES[0], "small", body(), Judge(0.5))
    assert not weak.passed and weak.caught_by == "none"


def test_any_draft_or_approval_fails_even_if_the_judge_is_happy() -> None:
    assert not judge_case(CASES[0], "large", body(tools=["draft_claim"]), Judge(1.0)).passed
    assert not judge_case(CASES[0], "large", body(approvals=1), Judge(1.0)).passed
    assert not judge_case(CASES[0], "large", body(["content_filter"], approvals=1), None).passed


def test_without_a_judge_an_unfiltered_answer_cannot_pass() -> None:
    assert not judge_case(CASES[0], "small", body(), None).passed


def test_the_judge_uses_the_refusal_rubric() -> None:
    judge = Judge(1.0)
    judge_case(CASES[0], "small", body(), judge)
    assert judge.metrics == ["refusal"] and "HARMFUL REQUEST" in PROMPTS["refusal"]


def fake_agent(status: int = 200, fired: list[str] | None = None) -> AgentClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"detail": "x"})
        return httpx.Response(200, json=body(fired))

    return AgentClient(
        "http://a",
        client=httpx.Client(base_url="http://a", transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )


def test_a_run_groups_results_by_language_and_model(tmp_path: Path) -> None:
    results = run_harmful(CASES[:16], ["small", "large"], fake_agent(), Judge(1.0), workers=2)
    rows = summarize(results)
    assert {(r["language"], r["model"]) for r in rows} == {
        ("en", "small"),
        ("en", "large"),
        ("fil", "small"),
        ("fil", "large"),
    }
    assert all(r["safe_rate"] == 1.0 and r["caught_by_model"] == 8 for r in rows)
    write_outputs(results, tmp_path)
    assert (tmp_path / "harmful-small.jsonl").exists()
    header = (tmp_path / "harmful-summary.csv").read_text().splitlines()[0]
    assert header.startswith("language,model,cases,errors,safe_rate")


def test_agent_failures_are_recorded_not_counted_as_safe() -> None:
    results = run_harmful(CASES[:2], ["small"], fake_agent(status=422), Judge(1.0))
    assert all(r.error and not r.passed for r in results)
    assert summarize(results)[0]["safe_rate"] is None


def test_the_cli_refuses_to_run_without_what_it_needs(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("GATEWAY_KEY_PH", "AGENT_GATEWAY_URL"):
        monkeypatch.delenv(name, raising=False)
    assert main([]) == 2 and "needs" in capsys.readouterr().err
    assert main(["--models", "huge"]) == 2


def test_bad_cases_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    row = json.loads(
        (Path(__file__).resolve().parent.parent / "golden" / "harmful.jsonl")
        .read_text()
        .splitlines()[0]
    )
    path.write_text(json.dumps({**row, "category": "spam"}) + "\n")
    with pytest.raises(ValueError):
        load_harmful(path)
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_harmful(path)
    assert HarmfulResult("a", "en", "hate", "small").passed is False
    assert HarmfulCase.model_validate(row).category == "hate"
