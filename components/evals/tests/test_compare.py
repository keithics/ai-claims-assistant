import json
from pathlib import Path

import pytest

from evals.compare import RunStats, load_run, main, markdown


def write(directory: Path, rows: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "cases-small.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return directory


def row(i: int, **overrides: object) -> dict:
    base = {
        "id": f"c{i}",
        "case_type": "faq",
        "error": None,
        "input_tokens": 1000,
        "output_tokens": 100,
        "cached_tokens": 0,
        "cost_usd": 0.001,
        "latency_ms": 3000,
        "levers_fired": [],
        "scores": {"groundedness": 0.8, "relevance": 0.9, "tool_accuracy": 1.0, "safety_pass": 1.0},
    }
    return {**base, **overrides}


def test_a_run_is_summarised(tmp_path: Path) -> None:
    run = load_run(
        write(
            tmp_path / "a",
            [row(1), row(2, input_tokens=500, cached_tokens=100), row(3, error="boom")],
        )
    )
    assert (run.cases, run.errors) == (3, 1)
    assert run.input_tokens == 750 and run.output_tokens == 100
    assert run.cached_share == pytest.approx(100 / 1500)
    assert run.tokens == 850 and run.relevance == pytest.approx(0.9)


def test_status_cases_do_not_count_towards_groundedness(tmp_path: Path) -> None:
    run = load_run(
        write(
            tmp_path / "a",
            [
                row(1),
                row(2, case_type="claim_status", scores={"groundedness": 0.0, "relevance": 1.0}),
            ],
        )
    )
    assert run.groundedness == pytest.approx(0.8)


def test_fired_levers_are_counted(tmp_path: Path) -> None:
    run = load_run(
        write(tmp_path / "a", [row(1, levers_fired=["x"]), row(2, levers_fired=["x", "y"])])
    )
    assert run.levers_fired == {"x": 2, "y": 1}


def test_the_comparison_shows_changes_in_tokens_and_quality(tmp_path: Path) -> None:
    base = load_run(write(tmp_path / "base", [row(1), row(2)]), label="baseline")
    cand = load_run(
        write(
            tmp_path / "cand",
            [
                row(
                    1,
                    input_tokens=800,
                    scores={
                        "groundedness": 0.7,
                        "relevance": 0.9,
                        "tool_accuracy": 1.0,
                        "safety_pass": 1.0,
                    },
                ),
                row(2, input_tokens=800),
            ],
        ),
        label="trim",
    )
    text = markdown(base, cand)
    assert "### trim vs baseline" in text
    assert "| Input tokens per case | 1000 | 800 | -20.0% |" in text
    assert "| Groundedness (doc-based cases) | 0.800 | 0.750 | -0.050 |" in text


def test_the_cli_needs_both_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = write(tmp_path / "a", [row(1)])
    assert main([str(good), str(tmp_path / "missing")]) == 2
    assert "no cases-small.jsonl" in capsys.readouterr().err
    assert main([str(good), str(good)]) == 0
    assert "### a vs a" in capsys.readouterr().out


def test_stats_without_scores_do_not_crash() -> None:
    stats = RunStats("x", 0, 0, 0.0, 0.0, 0.0, 0.0, None, None, None, None, 0.0, {})
    assert "n/a" in markdown(stats, stats)
