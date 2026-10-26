import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from agent_app.main import _topics
from agent_app.scope import CLAIM_ID, ScopeGuard
from country_packs import load_country_packs
from rag import OpenAIEmbedder, load_policy_documents
from shared import gateway_keys_from_env

GOLDEN = Path(__file__).resolve().parents[1] / "components" / "evals" / "golden"
IN_SCOPE_TYPES = ("faq", "country_rule", "claim_status", "claim_filing", "code_switch")


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (GOLDEN / name).read_text().splitlines() if line.strip()]


def pct(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * (len(ordered) - 1)))]


def margin_of(guard: ScopeGuard, row: dict) -> float:
    inside, outside = guard.score(row["input"], row["country"])
    return inside - outside


def main() -> int:
    parser = argparse.ArgumentParser(description="Score in-scope and off-topic prompts.")
    parser.add_argument("--gateway-url", default=os.environ.get("AGENT_GATEWAY_URL", ""))
    args = parser.parse_args()
    keys = gateway_keys_from_env(os.environ)
    if not args.gateway_url or not keys:
        print("tune: needs AGENT_GATEWAY_URL and GATEWAY_KEY_<COUNTRY>", file=sys.stderr)
        return 2
    packs = load_country_packs()
    docs = {d.doc_id: d for d in load_policy_documents(packs=packs)}
    embedder = OpenAIEmbedder(args.gateway_url, keys, "embedding", "2024-10-21", app="agent_app")
    guard = ScopeGuard(embedder, _topics(docs), margin=0.0)

    in_scope = [r for r in rows("golden.jsonl") if r["case_type"] in IN_SCOPE_TYPES]
    in_scope = [r for r in in_scope if not CLAIM_ID.search(r["input"])]
    adversarial = [r for r in rows("golden.jsonl") if r["case_type"] == "adversarial"]
    off = rows("off_topic.jsonl")
    scored = {
        "in_scope": [(r, margin_of(guard, r)) for r in in_scope],
        "adversarial": [(r, margin_of(guard, r)) for r in adversarial],
        "off_topic": [(r, margin_of(guard, r)) for r in off],
    }
    for name, items in scored.items():
        values = [s for _, s in items]
        print(
            f"{name:<12} n={len(values):<4} min={min(values):.3f} p5={pct(values, 0.05):.3f} "
            f"median={statistics.median(values):.3f} p95={pct(values, 0.95):.3f} "
            f"max={max(values):.3f}"
        )
    print("\nmargin sweep (blocked = in-scope minus off-topic similarity < margin):")
    for t in [x / 100 for x in range(-10, 14, 2)]:
        missed = sum(s < t for _, s in scored["in_scope"])
        caught = sum(s < t for _, s in scored["off_topic"])
        print(
            f"  {t:.2f}: in-scope wrongly blocked {missed}/{len(scored['in_scope'])}, "
            f"off-topic blocked {caught}/{len(scored['off_topic'])}"
        )
    low = sorted(scored["in_scope"], key=lambda p: p[1])[:6]
    print("\nlowest in-scope scores:")
    for r, s in low:
        print(f"  {s:.3f} {r['id']} {r['input'][:60]}")
    high = sorted(scored["off_topic"], key=lambda p: -p[1])[:6]
    print("highest off-topic scores:")
    for r, s in high:
        print(f"  {s:.3f} {r['id']} {r['input'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
