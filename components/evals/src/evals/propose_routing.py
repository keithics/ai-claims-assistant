import argparse
import sys
from pathlib import Path

from evals.propose import DEFAULT_GATE, load_gate, load_results, propose, render_yaml
from router import RoutingConfigError, parse_routing_config

RESULTS = Path(__file__).resolve().parents[2] / "results"
CURRENT = Path(__file__).resolve().parents[3] / "router" / "routing.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="propose-routing")
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--current", type=Path, default=CURRENT)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    small = args.results / "cases-small.jsonl"
    if not small.exists():
        print(
            f"propose-routing: {small} not found; run `run-evals --models small,large` first",
            file=sys.stderr,
        )
        return 2
    try:
        current = parse_routing_config(args.current.read_text(encoding="utf-8"))
    except (OSError, RoutingConfigError) as exc:
        print(f"propose-routing: {exc}", file=sys.stderr)
        return 2
    large = args.results / "cases-large.jsonl"
    proposed, notes = propose(
        current,
        load_results(small),
        load_gate(args.gate),
        load_results(large) if large.exists() else None,
    )
    out = args.out or args.results / "routing.proposed.yaml"
    out.write_text(render_yaml(proposed, notes), encoding="utf-8")
    print(f"propose-routing: wrote {out} ({len(proposed.rules)} large-tier rule(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
