import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

POLICIES = Path(__file__).resolve().parent.parent / "policies"
TOKEN = re.compile(r"(\$\{[^}]*\}|%\{[^}]*\})")
SAMPLE_COUNTRIES = ["ph", "sg", "id", "th", "jp"]


def render_template(text: str, variables: dict[str, Any]) -> str:
    parts = _tokenize(text)
    out, _ = _render(parts, 0, variables, stop=())
    return out


def _tokenize(text: str) -> list[str]:
    parts = TOKEN.split(text)
    for i, part in enumerate(parts[:-1]):
        if part.startswith("%{") and part.endswith("~}"):
            parts[i + 1] = parts[i + 1].lstrip()
    return parts


def _directive(token: str) -> str:
    return token[2:-1].strip().rstrip("~").strip()


def _truthy(name: str, variables: dict[str, Any]) -> bool:
    if name.startswith("!"):
        return not variables[name[1:].strip()]
    return bool(variables[name])


def _render(
    parts: list[str], index: int, variables: dict[str, Any], stop: tuple[str, ...]
) -> tuple[str, int]:
    out = []
    while index < len(parts):
        part = parts[index]
        if part.startswith("${"):
            out.append(str(variables[part[2:-1].strip()]))
            index += 1
        elif part.startswith("%{"):
            directive = _directive(part)
            word = directive.split()[0]
            if word in stop:
                return "".join(out), index
            if word == "if":
                condition = _truthy(directive[2:].strip(), variables)
                body, index = _render(parts, index + 1, variables, ("else", "endif"))
                other = ""
                if _directive(parts[index]) == "else":
                    other, index = _render(parts, index + 1, variables, ("endif",))
                out.append(body if condition else other)
                index += 1
            elif word == "for":
                match = re.fullmatch(r"for (\w+) in (\w+)", directive)
                assert match, f"unsupported for directive: {part}"
                name, source = match.groups()
                end = index
                for item in variables[source]:
                    body, end = _render(parts, index + 1, {**variables, name: item}, ("endfor",))
                    out.append(body)
                if not variables[source]:
                    _, end = _render(parts, index + 1, {**variables, name: ""}, ("endfor",))
                index = end + 1
            else:
                raise AssertionError(f"unsupported directive: {part}")
        else:
            out.append(part)
            index += 1
    return "".join(out), index


@pytest.fixture
def render() -> Callable[..., str]:
    def _render_policy(name: str, **overrides: Any) -> str:
        variables = {**defaults(), **overrides}
        return render_template((POLICIES / f"{name}.xml.tftpl").read_text(), variables)

    return _render_policy


def defaults() -> dict[str, Any]:
    return {
        "restrict_to_cloudflare": True,
        "cloudflare_ips": (POLICIES / "cloudflare-ips.xml").read_text(),
        "extra_allowed_addresses": [],
        "personal_data_headers": ["x-user-email", "x-forwarded-for"],
        "country": "ph",
        "tokens_per_minute": 10000,
        "token_quota": 500000,
        "token_quota_period": "Monthly",
        "allowed_countries": SAMPLE_COUNTRIES,
        "allowed_apps": ["agent_app", "evals"],
        "allowed_models": ["small-a", "small-b", "large", "embedding"],
        "allowed_route_tiers": ["small", "large"],
        "metric_namespace": "kalayaan",
        "semantic_cache_enabled": False,
        "semantic_cache_threshold": "0.05",
        "semantic_cache_max_messages": 3,
        "semantic_cache_ttl_seconds": 3600,
        "embeddings_backend_id": "embeddings",
        "model_backend_id": "small-pool",
        "retry_count": 2,
        "max_concurrent_per_country": 8,
        "calls_per_minute": 120,
        "claims_backend_id": "claims-api",
    }
