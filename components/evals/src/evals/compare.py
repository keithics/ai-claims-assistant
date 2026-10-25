import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunStats:
    label: str
    cases: int
    errors: int
    input_tokens: float
    output_tokens: float
    cached_share: float
    cost_usd: float
    groundedness: float | None
    relevance: float | None
    tool_accuracy: float | None
    safety: float | None
    p50_ms: float
    levers_fired: dict[str, int]

    @property
    def tokens(self) -> float:
        return self.input_tokens + self.output_tokens


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def load_run(directory: Path, model: str = "small", label: str | None = None) -> RunStats:
    rows = [
        json.loads(line)
        for line in (directory / f"cases-{model}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ok = [r for r in rows if not r.get("error")]

    def scores(name: str, types: tuple[str, ...] | None = None) -> list[float]:
        return [
            r["scores"][name]
            for r in ok
            if r["scores"].get(name) is not None and (types is None or r["case_type"] in types)
        ]

    input_total = sum(r["input_tokens"] for r in ok)
    fired: dict[str, int] = {}
    for r in ok:
        for name in r.get("levers_fired", []):
            fired[name] = fired.get(name, 0) + 1
    return RunStats(
        label=label or directory.name,
        cases=len(rows),
        errors=len(rows) - len(ok),
        input_tokens=_mean([float(r["input_tokens"]) for r in ok]) or 0.0,
        output_tokens=_mean([float(r["output_tokens"]) for r in ok]) or 0.0,
        cached_share=(sum(r.get("cached_tokens", 0) for r in ok) / input_total)
        if input_total
        else 0.0,
        cost_usd=_mean([r["cost_usd"] for r in ok]) or 0.0,
        groundedness=_mean(scores("groundedness", ("faq", "country_rule", "code_switch"))),
        relevance=_mean(scores("relevance")),
        tool_accuracy=_mean(scores("tool_accuracy")),
        safety=_mean(scores("safety_pass")),
        p50_ms=statistics.median([r["latency_ms"] for r in ok]) if ok else 0.0,
        levers_fired=fired,
    )


def _pct(new: float, old: float) -> str:
    return "n/a" if old == 0 else f"{(new - old) / old * 100:+.1f}%"


def _score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _delta(new: float | None, old: float | None) -> str:
    return "n/a" if new is None or old is None else f"{new - old:+.3f}"


def markdown(baseline: RunStats, candidate: RunStats) -> str:
    rows = [
        (
            "Input tokens per case",
            f"{baseline.input_tokens:.0f}",
            f"{candidate.input_tokens:.0f}",
            _pct(candidate.input_tokens, baseline.input_tokens),
        ),
        (
            "Output tokens per case",
            f"{baseline.output_tokens:.0f}",
            f"{candidate.output_tokens:.0f}",
            _pct(candidate.output_tokens, baseline.output_tokens),
        ),
        (
            "Cached share of input",
            f"{baseline.cached_share:.1%}",
            f"{candidate.cached_share:.1%}",
            f"{(candidate.cached_share - baseline.cached_share) * 100:+.1f} pt",
        ),
        (
            "Cost per case (USD)",
            f"{baseline.cost_usd:.6f}",
            f"{candidate.cost_usd:.6f}",
            _pct(candidate.cost_usd, baseline.cost_usd),
        ),
        (
            "Groundedness (doc-based cases)",
            _score(baseline.groundedness),
            _score(candidate.groundedness),
            _delta(candidate.groundedness, baseline.groundedness),
        ),
        (
            "Relevance",
            _score(baseline.relevance),
            _score(candidate.relevance),
            _delta(candidate.relevance, baseline.relevance),
        ),
        (
            "Tool accuracy",
            _score(baseline.tool_accuracy),
            _score(candidate.tool_accuracy),
            _delta(candidate.tool_accuracy, baseline.tool_accuracy),
        ),
        (
            "Safety pass rate",
            _score(baseline.safety),
            _score(candidate.safety),
            _delta(candidate.safety, baseline.safety),
        ),
        (
            "Latency p50 (ms)",
            f"{baseline.p50_ms:.0f}",
            f"{candidate.p50_ms:.0f}",
            _pct(candidate.p50_ms, baseline.p50_ms),
        ),
        ("Errored cases", str(baseline.errors), str(candidate.errors), ""),
    ]
    lines = [
        f"### {candidate.label} vs {baseline.label}",
        "",
        f"Cases: {baseline.cases} baseline, {candidate.cases} candidate. "
        f"Levers that fired: {candidate.levers_fired or 'none'}.",
        "",
        "| Metric | Baseline | Candidate | Change |",
        "|---|---|---|---|",
    ]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compare-runs")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--model", default="small")
    args = parser.parse_args(argv)
    for directory in (args.baseline, args.candidate):
        if not (directory / f"cases-{args.model}.jsonl").exists():
            print(f"compare-runs: no cases-{args.model}.jsonl in {directory}", file=sys.stderr)
            return 2
    print(markdown(load_run(args.baseline, args.model), load_run(args.candidate, args.model)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
