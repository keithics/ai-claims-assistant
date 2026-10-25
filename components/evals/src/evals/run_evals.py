import argparse
import os
import sys
from pathlib import Path

from evals.golden import DEFAULT_PATH, LANGUAGES, load_golden
from evals.runner import (
    AgentClient,
    load_case_results,
    rescore,
    run_all,
    select_cases,
    summarize,
    write_outputs,
)
from evals.scorers.judge import GatewayJudge
from shared import gateway_keys_from_env

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "results"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-evals", description="Run the golden set.")
    parser.add_argument("--models", default="small,large", help="tiers to compare")
    parser.add_argument("--languages", default="all", help="all or a comma list")
    parser.add_argument("--sample", type=int, help="run only N cases, spread over languages")
    parser.add_argument("--agent-url", default=os.environ.get("EVALS_AGENT_URL", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("AGENT_GATEWAY_URL", ""))
    parser.add_argument("--golden", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--judge-deployment", default="small-a")
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="re-score saved cases-*.jsonl in --out without calling the agent again",
    )
    parser.add_argument(
        "--levers",
        default=None,
        help="comma list of token levers to switch on for this run (empty = all off)",
    )
    parser.add_argument("--no-judge", action="store_true", help="skip model-graded scores")
    args = parser.parse_args(argv)

    levers = None if args.levers is None else [x for x in args.levers.split(",") if x.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    bad_models = [m for m in models if m not in ("small", "large")]
    languages = list(LANGUAGES) if args.languages == "all" else args.languages.split(",")
    bad_languages = [lang for lang in languages if lang not in LANGUAGES]
    if bad_models or bad_languages or not models:
        print(
            f"run-evals: unknown model(s) {bad_models} or language(s) {bad_languages}",
            file=sys.stderr,
        )
        return 2
    if not args.agent_url:
        print(
            "run-evals: pass --agent-url or set EVALS_AGENT_URL (agent_app must run with "
            "AGENT_ALLOW_TIER_OVERRIDE=1)",
            file=sys.stderr,
        )
        return 2
    judge = None
    if not args.no_judge:
        keys = gateway_keys_from_env(os.environ)
        if not args.gateway_url or not keys:
            print(
                "run-evals: the judge needs --gateway-url and GATEWAY_KEY_<COUNTRY> "
                "(or pass --no-judge)",
                file=sys.stderr,
            )
            return 2
        judge = GatewayJudge(args.gateway_url, keys, deployment=args.judge_deployment)

    if args.rescore:
        golden = {c.id: c for c in load_golden(args.golden)}
        saved: list = []
        for model in models:
            saved += load_case_results(args.out / f"cases-{model}.jsonl")
        results = rescore(saved, golden, AgentClient(args.agent_url), judge)
        write_outputs(results, args.out)
        print(f"run-evals: rescored {len(results)} saved case(s) in {args.out}")
        return 0

    cases = select_cases(load_golden(args.golden), languages, args.sample)
    print(f"run-evals: {len(cases)} cases x {len(models)} model(s)", flush=True)
    results = run_all(
        cases, models, AgentClient(args.agent_url, levers=levers), judge, args.workers
    )
    write_outputs(results, args.out)
    errors = sum(r.error is not None for r in results)
    for row in summarize(results):
        print(
            f"{row['language']:>3} {row['model']:<6} cases={row['cases']} errors={row['errors']} "
            f"tool={row['tool_accuracy']} safety={row['safety_pass_rate']} "
            f"cost={row['cost_per_case_usd']}"
        )
    print(f"run-evals: wrote {args.out}/summary.csv ({errors} errored case(s))")
    return 1 if errors == len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
