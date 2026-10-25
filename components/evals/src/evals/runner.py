import csv
import json
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from evals.golden import CASE_TYPES, LANGUAGES, GoldenCase
from evals.scorers.custom import (
    answer_language,
    polite_form,
    safety_pass,
    source_hit,
    tool_accuracy,
)
from evals.scorers.judge import METRICS, Judge

SUMMARY_COLUMNS = (
    "language",
    "model",
    "groundedness",
    "relevance",
    "tool_accuracy",
    "safety_pass_rate",
    "p50_ms",
    "p95_ms",
    "cost_per_case_usd",
    "tokens_per_case",
)
DETAIL_COLUMNS = (
    "language",
    "model",
    "cases",
    "errors",
    "coherence",
    "language_fit",
    "polite_form",
    "source_hit",
)
BASELINE_COLUMNS = ("language", "model")
RETRY_WAITS = (15.0, 30.0, 60.0)


@dataclass
class CaseResult:
    id: str
    language: str
    country: str
    case_type: str
    model: str
    deployment: str = ""
    answer: str = ""
    tools_used: list[str] = field(default_factory=list)
    cited_docs: list[str] = field(default_factory=list)
    pending_approvals: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    fallback_used: bool = False
    cached_tokens: int = 0
    levers_fired: list[str] = field(default_factory=list)
    scores: dict[str, float | None] = field(default_factory=dict)
    judge_reasons: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def build_history(case: GoldenCase, pool: Sequence[GoldenCase], turns: int) -> list[dict[str, str]]:
    earlier = [
        c
        for c in pool
        if c.id != case.id
        and c.country == case.country
        and c.language == case.language
        and c.case_type in ("faq", "country_rule")
    ][:turns]
    history: list[dict[str, str]] = []
    for prior in earlier:
        history.append({"role": "user", "content": prior.input})
        history.append({"role": "assistant", "content": prior.expected_answer[:400]})
    return history


class AgentClient:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        levers: Sequence[str] | None = None,
        history_turns: int = 0,
        pool: Sequence[GoldenCase] = (),
    ) -> None:
        self._history_turns = history_turns
        self._pool = list(pool)
        self._sleep = sleep
        self._levers = list(levers) if levers is not None else None
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=120.0)

    def chat(self, case: GoldenCase, tier: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": case.input,
            "country": case.country,
            "language": case.language,
            "tier_override": tier,
        }
        if self._levers is not None:
            payload["levers"] = self._levers
        if self._history_turns:
            payload["history"] = build_history(case, self._pool, self._history_turns)
        last: httpx.Response | None = None
        for attempt in range(len(RETRY_WAITS) + 1):
            last = self._http.post("/chat", json=payload)
            if last.status_code < 500 and last.status_code != 429:
                break
            if attempt < len(RETRY_WAITS):
                self._sleep(RETRY_WAITS[attempt])
        assert last is not None
        if last.status_code != 200:
            raise RuntimeError(f"agent_app returned {last.status_code}: {last.text[:200]}")
        body: dict[str, Any] = last.json()
        return body

    def document(self, doc_id: str) -> str:
        response = self._http.get(f"/documents/{doc_id}")
        if response.status_code != 200:
            return ""
        return str(response.json().get("body", ""))


def select_cases(
    cases: Sequence[GoldenCase], languages: Sequence[str], sample: int | None
) -> list[GoldenCase]:
    wanted = [c for c in cases if c.language in languages]
    if sample is None or sample >= len(wanted):
        return wanted
    by_language: dict[str, list[GoldenCase]] = {lang: [] for lang in languages}
    for case in wanted:
        by_language[case.language].append(case)
    for language, items in by_language.items():
        items.sort(key=lambda c: (CASE_TYPES.index(c.case_type), c.id))
        stride: list[GoldenCase] = []
        buckets = [[c for c in items if c.case_type == t] for t in CASE_TYPES]
        for position in range(5):
            for bucket in buckets:
                if position < len(bucket):
                    stride.append(bucket[position])
        by_language[language] = stride
    chosen: list[GoldenCase] = []
    position = 0
    while len(chosen) < sample:
        progressed = False
        for language in languages:
            items = by_language.get(language, [])
            if position < len(items) and len(chosen) < sample:
                chosen.append(items[position])
                progressed = True
        if not progressed:
            break
        position += 1
    return chosen


def grading_context(case: GoldenCase, cited: Sequence[str], agent: AgentClient) -> str:
    documents = [agent.document(doc_id) for doc_id in dict.fromkeys(cited)]
    if case.expected_tool == "get_claim_status":
        documents.append(
            "CLAIMS SYSTEM RESULT (authoritative, from the get_claim_status tool):\n"
            + case.expected_answer
        )
    return "\n\n".join(documents)


def deterministic_scores(
    case: GoldenCase, answer: str, tools: Sequence[str], cited: Sequence[str], pending: int
) -> dict[str, float | None]:
    return {
        "tool_accuracy": tool_accuracy(case.expected_tool, tools),
        "safety_pass": float(
            safety_pass(
                case_type=case.case_type,
                country=case.country,
                language=case.language,
                user_input=case.input,
                answer=answer,
                tools_used=tools,
                pending_approvals=[None] * pending,
            )
        ),
        "language_fit": answer_language(answer, case.language),
        "source_hit": source_hit(case.expected_source, cited),
        "polite_form": polite_form(answer) if case.language == "ja" else None,
    }


def rescore(
    results: Sequence[CaseResult],
    cases: Mapping[str, GoldenCase],
    agent: AgentClient,
    judge: Judge | None,
    *,
    rejudge_types: Sequence[str] = ("claim_status",),
) -> list[CaseResult]:
    for result in results:
        case = cases[result.id]
        if result.error is not None:
            continue
        fresh = deterministic_scores(
            case, result.answer, result.tools_used, result.cited_docs, result.pending_approvals
        )
        result.scores.update(fresh)
        if judge is not None and result.case_type in rejudge_types:
            context = grading_context(case, result.cited_docs, agent)
            for metric in METRICS:
                graded = judge.grade(
                    metric,
                    country=case.country,
                    question=case.input,
                    answer=result.answer,
                    context=context,
                    reference=case.expected_answer,
                )
                result.scores[metric] = graded.score
                result.judge_reasons[metric] = graded.reason
    return list(results)


def load_case_results(path: Path) -> list[CaseResult]:
    return [
        CaseResult(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_case(
    case: GoldenCase,
    model: str,
    body: Mapping[str, Any],
    agent: AgentClient,
    judge: Judge | None,
) -> CaseResult:
    usage = body["usage"]
    answer: str = body["answer"]
    tools = list(usage.get("tool_calls", []))
    cited = [c["doc_id"] for c in body.get("citations", [])]
    pending = body.get("pending_approvals", [])
    result = CaseResult(
        id=case.id,
        language=case.language,
        country=case.country,
        case_type=case.case_type,
        model=model,
        deployment=usage["route"]["deployment"],
        answer=answer,
        tools_used=tools,
        cited_docs=cited,
        pending_approvals=len(pending),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cost_usd=usage["cost_usd"],
        latency_ms=usage["latency_ms"],
        fallback_used=bool(usage.get("fallback_used", False)),
        cached_tokens=usage.get("cached_tokens", 0),
        levers_fired=list(usage.get("levers_fired", [])),
    )
    result.scores = deterministic_scores(case, answer, tools, cited, len(pending))
    if judge is not None:
        context = grading_context(case, cited, agent)
        for metric in METRICS:
            graded = judge.grade(
                metric,
                country=case.country,
                question=case.input,
                answer=answer,
                context=context,
                reference=case.expected_answer,
            )
            result.scores[metric] = graded.score
            result.judge_reasons[metric] = graded.reason
    return result


def run_case(case: GoldenCase, model: str, agent: AgentClient, judge: Judge | None) -> CaseResult:
    try:
        body = agent.chat(case, model)
        return score_case(case, model, body, agent, judge)
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            id=case.id,
            language=case.language,
            country=case.country,
            case_type=case.case_type,
            model=model,
            error=f"{type(exc).__name__}: {exc}"[:300],
        )


def run_all(
    cases: Sequence[GoldenCase],
    models: Sequence[str],
    agent: AgentClient,
    judge: Judge | None,
    workers: int = 4,
) -> list[CaseResult]:
    jobs = [(case, model) for model in models for case in cases]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: run_case(job[0], job[1], agent, judge), jobs))


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.fmean(present) if present else None


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))] if ordered else 0.0


def summarize(results: Sequence[CaseResult]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[CaseResult]] = defaultdict(list)
    for result in results:
        groups[(result.language, result.model)].append(result)
    rows: list[dict[str, Any]] = []
    for language in LANGUAGES:
        for (lang, model), items in sorted(groups.items()):
            if lang != language:
                continue
            ok = [r for r in items if r.error is None]
            adversarial = [r for r in ok if r.case_type == "adversarial"]
            rows.append(
                {
                    "language": lang,
                    "model": model,
                    "groundedness": _mean([r.scores.get("groundedness") for r in ok]),
                    "relevance": _mean([r.scores.get("relevance") for r in ok]),
                    "tool_accuracy": _mean([r.scores.get("tool_accuracy") for r in ok]),
                    "safety_pass_rate": _mean(
                        [r.scores.get("safety_pass") for r in (adversarial or ok)]
                    ),
                    "p50_ms": _percentile([r.latency_ms for r in ok], 0.5),
                    "p95_ms": _percentile([r.latency_ms for r in ok], 0.95),
                    "cost_per_case_usd": _mean([r.cost_usd for r in ok]),
                    "tokens_per_case": _mean([r.input_tokens + r.output_tokens for r in ok]),
                    "cases": len(items),
                    "errors": len(items) - len(ok),
                    "coherence": _mean([r.scores.get("coherence") for r in ok]),
                    "language_fit": _mean([r.scores.get("language_fit") for r in ok]),
                    "polite_form": _mean([r.scores.get("polite_form") for r in ok]),
                    "source_hit": _mean([r.scores.get("source_hit") for r in ok]),
                }
            )
    return rows


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_outputs(results: Sequence[CaseResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for model in sorted({r.model for r in results}):
        path = out_dir / f"cases-{model}.jsonl"
        path.write_text(
            "".join(
                json.dumps(asdict(r), ensure_ascii=False) + "\n"
                for r in results
                if r.model == model
            ),
            encoding="utf-8",
        )
    rows = summarize(results)
    for name, columns in (
        ("summary.csv", SUMMARY_COLUMNS),
        ("summary_detail.csv", BASELINE_COLUMNS + DETAIL_COLUMNS[2:]),
    ):
        with (out_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([_format(row[c]) for c in columns])
