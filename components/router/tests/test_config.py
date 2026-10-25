import pytest
from pydantic import ValidationError

from router import RouteRequest, RoutingConfigError, RoutingRule, parse_routing_config

LIMITS = """
output_limits:
  faq: {small: 1, large: 2}
  country_rule: {small: 1, large: 2}
  claim_status: {small: 1, large: 2}
  claim_filing: {small: 1, large: 2}
  other: {small: 1, large: 2}
"""


def make(body: str) -> str:
    return "version: 1\n" + body + LIMITS


def test_a_valid_config_parses() -> None:
    cfg = parse_routing_config(make("deployments: {small: [a], large: [b]}\n"))
    assert cfg.default_tier == "small" and cfg.rules == []


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("a: [", "not valid YAML"),
        ("- 1\n- 2\n", "must be a YAML mapping"),
        (make("deployments: {small: [a]}\n"), "at least one entry for tier 'large'"),
        (make("deployments: {small: [], large: [b]}\n"), "at least one entry for tier 'small'"),
        (make("deployments: {small: [a, a], large: [b]}\n"), "repeat a name"),
        (make("deployments: {small: [a], large: [b]}\nsurprise: 1\n"), "surprise"),
        (
            "version: 1\ndeployments: {small: [a], large: [b]}\noutput_limits:\n"
            "  faq: {small: 1, large: 2}\n",
            "missing intent",
        ),
        (
            make("deployments: {small: [a], large: [b]}\nrules:\n  - {tier: small, reason: x}\n"),
            "at least one of",
        ),
        (
            make(
                "deployments: {small: [a], large: [b]}\nrules:\n"
                "  - {language: English, tier: small, reason: x}\n"
            ),
            "language must be",
        ),
        (
            make(
                "deployments: {small: [a], large: [b]}\nrules:\n"
                "  - {country: philippines, tier: small, reason: x}\n"
            ),
            "country must be",
        ),
        (
            make("deployments: {small: [a], large: [b]}\ndefault_tier: medium\n"),
            "default_tier",
        ),
    ],
)
def test_invalid_configs_are_rejected_with_a_reason(text: str, message: str) -> None:
    with pytest.raises(RoutingConfigError, match=message):
        parse_routing_config(text)


def test_valid_rule_fields_are_kept() -> None:
    rule = RoutingRule(language="ja", country="jp", intent="faq", tier="large", reason="x")
    assert (rule.language, rule.country, rule.intent) == ("ja", "jp", "faq")


def test_requests_are_frozen_and_reject_unknown_values() -> None:
    request = RouteRequest(country="ph", language="en", intent="faq", risk="low")
    with pytest.raises(ValidationError):
        request.language = "th"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RouteRequest(country="ph", language="en", intent="chitchat", risk="low")  # type: ignore[arg-type]
