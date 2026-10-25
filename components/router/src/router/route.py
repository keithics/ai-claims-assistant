from router.models import (
    BudgetState,
    RouteDecision,
    RouteRequest,
    RoutingConfig,
    RoutingRule,
    Tier,
)


def _matches(rule: RoutingRule, request: RouteRequest) -> bool:
    return (
        (rule.language is None or rule.language == request.language)
        and (rule.intent is None or rule.intent == request.intent)
        and (rule.country is None or rule.country == request.country)
    )


def _handoff(reason: str) -> RouteDecision:
    return RouteDecision(tier="handoff", deployment=None, reason=reason)


def _decide(
    tier: Tier, reason: str, request: RouteRequest, cfg: RoutingConfig, budget: BudgetState
) -> RouteDecision:
    own = cfg.deployments[tier]
    other_tier: Tier = "large" if tier == "small" else "small"
    fallbacks = list(own[1:])
    crosses = other_tier in request.allowed_tiers and request.risk == "low"
    if other_tier == "large" and budget != "ok":
        crosses = False
    if crosses:
        fallbacks.extend(cfg.deployments[other_tier])
    return RouteDecision(
        tier=tier,
        deployment=own[0],
        reason=reason,
        fallbacks=tuple(fallbacks),
        max_output_tokens=getattr(cfg.output_limits[request.intent], tier),
    )


def route(request: RouteRequest, cfg: RoutingConfig, budget: BudgetState) -> RouteDecision:
    if request.risk == "high":
        if budget == "exceeded":
            return _handoff("high risk and the budget is exceeded: hand off to a human")
        if "large" not in request.allowed_tiers:
            return _handoff(f"high risk and {request.country} does not allow the large tier")
        return _decide("large", "high risk always uses the large tier", request, cfg, budget)

    tier: Tier = cfg.default_tier
    reason = f"default tier {cfg.default_tier}"
    for rule in cfg.rules:
        if _matches(rule, request):
            tier, reason = rule.tier, rule.reason
            break

    if tier == "large" and budget != "ok":
        tier = "small"
        reason = f"budget {budget}: downgraded from large to small ({reason})"

    if tier not in request.allowed_tiers:
        remaining: list[Tier] = [t for t in request.allowed_tiers if t != tier]
        if not remaining:
            return _handoff(f"{request.country} allows no model tier")
        tier = remaining[0]
        reason = f"{request.country} does not allow the preferred tier; using {tier}"

    return _decide(tier, reason, request, cfg, budget)
