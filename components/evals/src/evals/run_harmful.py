import argparse
import os
import sys
from pathlib import Path

from evals.harmful import (
    CATEGORIES,
    load_harmful,
    run_harmful,
    summarize,
    write_outputs,
)
from evals.runner import AgentClient
from evals.scorers.judge import GatewayJudge
from shared import gateway_keys_from_env

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "results" / "runs" / "harmful"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-harmful", description="Run the harmful-prompt set.")
    parser.add_argument("--models", default="small,large")
    parser.add_argument("--agent-url", default=os.environ.get("EVALS_AGENT_URL", ""))
    parser.add_argument("--gateway-url", default=os.environ.get("AGENT_GATEWAY_URL", ""))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--judge-deployment", default="small-a")
    args = parser.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models or any(m not in ("small", "large") for m in models):
        print("run-harmful: --models must be small, large or both", file=sys.stderr)
        return 2
    keys = gateway_keys_from_env(os.environ)
    if not args.agent_url or not args.gateway_url or not keys:
        print(
            "run-harmful: needs --agent-url, --gateway-url and GATEWAY_KEY_<COUNTRY>",
            file=sys.stderr,
        )
        return 2
    judge = GatewayJudge(args.gateway_url, keys, deployment=args.judge_deployment)
    cases = load_harmful()
    print(f"run-harmful: {len(cases)} prompts x {len(models)} model(s)", flush=True)
    results = run_harmful(cases, models, AgentClient(args.agent_url), judge, args.workers)
    write_outputs(results, args.out)
    for row in summarize(results):
        print(row)
    print(f"run-harmful: wrote {args.out}; categories: {', '.join(CATEGORIES)}")
    return 0 if all(r.error is None for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
