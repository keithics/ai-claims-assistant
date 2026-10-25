import argparse
import os
import statistics
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

PROMPT = "Write a numbered list of 40 short tips for filing an insurance claim. Number every tip."
DEPLOYMENT_HEADERS = ("x-ms-deployment-name", "x-ratelimit-key")


@dataclass
class Sample:
    status: int
    seconds: float
    deployment: str = ""
    tokens: int = 0


@dataclass
class CountryResult:
    country: str
    rate: float
    samples: list[Sample] = field(default_factory=list)

    def count(self, status: int) -> int:
        return sum(1 for s in self.samples if s.status == status)

    @property
    def ok(self) -> int:
        return self.count(200)

    @property
    def limited(self) -> int:
        return self.count(429)

    @property
    def other(self) -> int:
        return len(self.samples) - self.ok - self.limited

    @property
    def other_statuses(self) -> dict[int, int]:
        counts = Counter(s.status for s in self.samples if s.status not in (200, 429))
        return dict(sorted(counts.items()))

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.samples)

    @property
    def deployments(self) -> Counter[str]:
        return Counter(s.deployment for s in self.samples if s.deployment)

    def first_limited_at(self, start: float) -> float | None:
        times = [s.seconds for s in self.samples if s.status == 429]
        return min(times) - start if times else None


def parse_rates(text: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for part in text.split(","):
        country, _, value = part.partition("=")
        country = country.strip().lower()
        if not country or not value:
            raise ValueError(f"bad rate {part!r}; expected country=requests_per_second")
        rate = float(value)
        if rate <= 0:
            raise ValueError(f"rate for {country} must be positive")
        rates[country] = rate
    return rates


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def classify(results: list[CountryResult]) -> tuple[list[str], list[str]]:
    limited = [r.country for r in results if r.limited > 0]
    healthy = [r.country for r in results if r.limited == 0 and r.ok > 0]
    return limited, healthy


def render(results: list[CountryResult], duration: float, max_tokens: int, gateway: str) -> str:
    limited, healthy = classify(results)
    lines = [
        "# Load test",
        "",
        f"Run at {datetime.now(UTC):%Y-%m-%d %H:%M} UTC against `{gateway}`, "
        f"{duration:.0f} s per country, up to {max_tokens} output tokens per request.",
        "",
        "| Country | Rate (req/s) | Sent | 200 | 429 | Other | Tokens | p50 s | p95 s | "
        "First 429 after (s) | Deployments seen |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        times = [s.seconds for s in r.samples if s.status == 200]
        first = r.first_limited_at(0.0)
        deployments = ", ".join(f"{k} x{v}" for k, v in sorted(r.deployments.items())) or "n/a"
        lines.append(
            f"| {r.country} | {r.rate:g} | {len(r.samples)} | {r.ok} | {r.limited} | {r.other} | "
            f"{r.tokens} | {statistics.median(times) if times else 0:.2f} | "
            f"{percentile(times, 0.95):.2f} | {'-' if first is None else f'{first:.0f}'} | "
            f"{deployments} |"
        )
    lines += [
        "",
        f"Hit their token limit: {', '.join(limited) or 'none'}. "
        f"Kept working with no 429: {', '.join(healthy) or 'none'}.",
    ]
    for r in results:
        if r.other_statuses:
            codes = ", ".join(f"{code} x{n}" for code, n in r.other_statuses.items())
            lines.append(f"Other statuses for {r.country} (0 = no response): {codes}.")
    return "\n".join(lines) + "\n"


def one_request(
    client: httpx.Client, gateway: str, country: str, key: str, max_tokens: int, api_version: str
) -> Sample:
    started = time.perf_counter()
    try:
        response = client.post(
            f"{gateway}/small/chat/completions",
            params={"api-version": api_version},
            headers={
                "api-key": key,
                "x-country": country,
                "x-app": "evals",
                "x-model": "small-a",
                "x-route-tier": "small",
            },
            json={
                "messages": [{"role": "user", "content": PROMPT}],
                "max_completion_tokens": max_tokens,
            },
        )
    except httpx.HTTPError:
        return Sample(0, time.perf_counter() - started)
    tokens = 0
    if response.status_code == 200:
        tokens = int(response.json().get("usage", {}).get("total_tokens", 0))
    return Sample(
        response.status_code,
        time.perf_counter() - started,
        next((response.headers[h] for h in DEPLOYMENT_HEADERS if h in response.headers), ""),
        tokens,
    )


def drive(
    rate: float,
    duration: float,
    pool: ThreadPoolExecutor,
    result: CountryResult,
    lock: threading.Lock,
    send: Callable[[], Sample],
) -> None:
    interval = 1.0 / rate
    end = time.perf_counter() + duration
    futures = []
    next_at = time.perf_counter()
    while time.perf_counter() < end:
        futures.append(pool.submit(send))
        next_at += interval
        time.sleep(max(0.0, next_at - time.perf_counter()))
    for future in futures:
        sample = future.result()
        with lock:
            result.samples.append(sample)


def run(
    gateway: str,
    keys: Mapping[str, str],
    rates: Mapping[str, float],
    duration: float,
    max_tokens: int,
    api_version: str,
) -> list[CountryResult]:
    results = [CountryResult(c, r) for c, r in rates.items()]
    lock = threading.Lock()
    client = httpx.Client(timeout=60.0, limits=httpx.Limits(max_connections=100))
    with ThreadPoolExecutor(max_workers=64) as pool:
        drivers = []
        for result in results:
            key = keys[result.country]

            def send(country: str = result.country, key: str = key) -> Sample:
                return one_request(client, gateway, country, key, max_tokens, api_version)

            thread = threading.Thread(
                target=drive,
                args=(result.rate, duration, pool, result, lock, send),
            )
            drivers.append(thread)
            thread.start()
        for thread in drivers:
            thread.join()
    client.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-country load against the model gateway.")
    parser.add_argument("--gateway-url", default=os.environ.get("AGENT_GATEWAY_URL", ""))
    parser.add_argument("--rates", default="ph=3,sg=0.2,th=0.2", help="country=requests/second,...")
    parser.add_argument("--duration", type=float, default=60.0, help="seconds per country")
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument("--api-version", default="2024-10-21")
    parser.add_argument("--report", type=Path, help="write the markdown report here")
    args = parser.parse_args()

    if not args.gateway_url:
        print("load-test: pass --gateway-url or set AGENT_GATEWAY_URL", file=sys.stderr)
        return 2
    try:
        rates = parse_rates(args.rates)
    except ValueError as exc:
        print(f"load-test: {exc}", file=sys.stderr)
        return 2
    keys = {
        name.removeprefix("GATEWAY_KEY_").lower(): value
        for name, value in os.environ.items()
        if name.startswith("GATEWAY_KEY_") and value
    }
    missing = [c for c in rates if c not in keys]
    if missing:
        print(f"load-test: no GATEWAY_KEY_<COUNTRY> for {', '.join(missing)}", file=sys.stderr)
        return 2

    results = run(
        args.gateway_url.rstrip("/"),
        keys,
        rates,
        args.duration,
        args.max_tokens,
        args.api_version,
    )
    report = render(results, args.duration, args.max_tokens, args.gateway_url)
    print(report)
    if args.report:
        args.report.write_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
