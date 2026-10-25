from pathlib import Path

import pytest

from router import (
    BudgetState,
    RouteDecision,
    RouteRequest,
    RoutingConfig,
    parse_routing_config,
    route,
)

CFG = parse_routing_config(
    """
version: 1
default_tier: small
deployments:
  small: [small-a, small-b]
  large: [large]
rules:
  - {language: ceb, tier: large, reason: Cebuano needs the large tier}
  - {intent: country_rule, country: jp, tier: large, reason: JP rules are subtle}
  - {intent: claim_filing, tier: large, reason: filing needs care}
output_limits:
  faq: {small: 300, large: 1200}
  country_rule: {small: 310, large: 1210}
  claim_status: {small: 200, large: 1000}
  claim_filing: {small: 500, large: 1500}
  other: {small: 320, large: 1220}
"""
)


def req(
    intent: str = "faq",
    risk: str = "low",
    language: str = "en",
    country: str = "ph",
    allowed: tuple[str, ...] = ("small", "large"),
) -> RouteRequest:
    return RouteRequest.model_validate(
        {
            "country": country,
            "language": language,
            "intent": intent,
            "risk": risk,
            "allowed_tiers": allowed,
        }
    )


def run(
    request: RouteRequest, budget: BudgetState = "ok", cfg: RoutingConfig = CFG
) -> RouteDecision:
    return route(request, cfg, budget)


@pytest.mark.parametrize(
    ("request_", "budget", "tier", "deployment"),
    [
        (req("faq"), "ok", "small", "small-a"),
        (req("claim_status"), "ok", "small", "small-a"),
        (req("faq", language="ceb"), "ok", "large", "large"),
        (req("country_rule", country="jp", language="ja"), "ok", "large", "large"),
        (req("country_rule", country="ph"), "ok", "small", "small-a"),
        (req("claim_filing"), "ok", "large", "large"),
        (req("faq", risk="high"), "ok", "large", "large"),
        (req("faq", risk="high"), "warn", "large", "large"),
        (req("claim_status", risk="high", language="th"), "ok", "large", "large"),
    ],
)
def test_tier_and_deployment(
    request_: RouteRequest, budget: BudgetState, tier: str, deployment: str
) -> None:
    decision = run(request_, budget)
    assert (decision.tier, decision.deployment) == (tier, deployment)
    assert decision.reason


def test_high_risk_never_downgrades_even_when_the_budget_is_in_warning() -> None:
    assert run(req(risk="high", language="en"), "warn").tier == "large"


def test_high_risk_with_an_exceeded_budget_hands_off_instead_of_downgrading() -> None:
    decision = run(req(risk="high"), "exceeded")
    assert decision.tier == "handoff"
    assert decision.deployment is None and decision.fallbacks == ()
    assert "hand off" in decision.reason


def test_high_risk_where_the_country_forbids_large_hands_off() -> None:
    decision = run(req(risk="high", allowed=("small",)))
    assert decision.tier == "handoff" and "does not allow the large tier" in decision.reason


@pytest.mark.parametrize("budget", ["warn", "exceeded"])
def test_low_risk_work_is_downgraded_to_small_when_the_budget_is_tight(
    budget: BudgetState,
) -> None:
    decision = run(req("claim_filing"), budget)
    assert decision.tier == "small" and decision.deployment == "small-a"
    assert f"budget {budget}" in decision.reason and "filing needs care" in decision.reason


def test_a_small_rule_is_not_marked_as_downgraded() -> None:
    assert "budget" not in run(req("faq"), "warn").reason


def test_first_matching_rule_wins() -> None:
    cfg = parse_routing_config(
        """
version: 1
deployments: {small: [s], large: [l]}
rules:
  - {language: en, tier: large, reason: first}
  - {language: en, tier: small, reason: second}
output_limits:
  faq: {small: 1, large: 2}
  country_rule: {small: 1, large: 2}
  claim_status: {small: 1, large: 2}
  claim_filing: {small: 1, large: 2}
  other: {small: 1, large: 2}
"""
    )
    decision = run(req(), cfg=cfg)
    assert decision.tier == "large" and decision.reason == "first"


def test_a_rule_needs_every_condition_it_names() -> None:
    assert run(req("country_rule", country="sg", language="en")).tier == "small"
    assert run(req("faq", country="jp", language="ja")).tier == "small"


def test_default_tier_can_be_large() -> None:
    cfg = CFG.model_copy(update={"default_tier": "large", "rules": []})
    assert run(req(), cfg=cfg).tier == "large"
    assert run(req(), "warn", cfg=cfg).tier == "small"


def test_small_falls_back_to_the_other_small_then_large_when_the_budget_is_ok() -> None:
    assert run(req("faq")).fallbacks == ("small-b", "large")


@pytest.mark.parametrize("budget", ["warn", "exceeded"])
def test_small_does_not_escalate_to_large_when_the_budget_is_tight(budget: BudgetState) -> None:
    assert run(req("faq"), budget).fallbacks == ("small-b",)


def test_small_does_not_escalate_to_large_where_large_is_forbidden() -> None:
    assert run(req("faq", allowed=("small",))).fallbacks == ("small-b",)


def test_low_risk_large_falls_back_to_small() -> None:
    decision = run(req("claim_filing"))
    assert decision.fallbacks == ("small-a", "small-b")


def test_low_risk_large_may_fall_back_to_small_even_where_small_is_the_only_other() -> None:
    assert run(req("claim_filing", allowed=("small", "large"))).fallbacks == ("small-a", "small-b")


def test_high_risk_has_no_small_fallback() -> None:
    assert run(req(risk="high")).fallbacks == ()


def test_large_with_small_forbidden_has_no_small_fallback() -> None:
    decision = run(req("claim_filing", allowed=("large",)))
    assert decision.tier == "large" and decision.fallbacks == ()


def test_a_forbidden_preferred_tier_switches_to_the_allowed_one() -> None:
    decision = run(req("claim_filing", allowed=("small",)))
    assert decision.tier == "small" and "does not allow the preferred tier" in decision.reason
    decision = run(req("faq", allowed=("large",)))
    assert decision.tier == "large" and decision.deployment == "large"


def test_no_allowed_tier_hands_off() -> None:
    decision = run(req("faq", allowed=()))
    assert decision.tier == "handoff" and "allows no model tier" in decision.reason


@pytest.mark.parametrize(
    ("intent", "tier", "expected"),
    [
        ("faq", "small", 300),
        ("country_rule", "small", 310),
        ("claim_status", "small", 200),
        ("other", "small", 320),
        ("claim_filing", "large", 1500),
    ],
)
def test_output_limits_come_from_config_per_intent_and_tier(
    intent: str, tier: str, expected: int
) -> None:
    decision = run(req(intent))
    assert decision.tier == tier and decision.max_output_tokens == expected


def test_route_is_deterministic_and_does_not_change_its_inputs() -> None:
    request = req("claim_filing")
    before = (request.model_dump(), CFG.model_dump())
    assert run(request) == run(request)
    assert (request.model_dump(), CFG.model_dump()) == before


def test_the_committed_routing_yaml_is_valid() -> None:
    path = Path(__file__).resolve().parent.parent / "routing.yaml"
    cfg = parse_routing_config(path.read_text())
    assert cfg.deployments["small"] and cfg.deployments["large"]
    assert run(req(), cfg=cfg).tier == "small"
