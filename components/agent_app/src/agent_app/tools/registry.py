import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from agent_app.llm import parse_arguments
from agent_app.tools import draft_claim, get_claim_status, search_policy
from agent_app.tools.base import ToolContext, ToolOutcome
from telemetry import tool_call

Runner = Callable[[Any, ToolContext], ToolOutcome]

TOOLS: dict[str, tuple[type[BaseModel], Runner]] = {
    "search_policy": (search_policy.SearchPolicyArgs, search_policy.run),
    "get_claim_status": (get_claim_status.ClaimStatusArgs, get_claim_status.run),
    "draft_claim": (draft_claim.DraftClaimArgs, draft_claim.run),
}

COMPACT_DESCRIPTIONS = {
    "search_policy": "Search the user's country policy documents.",
    "get_claim_status": "Get a claim's status by claim number.",
    "draft_claim": "Prepare a claim draft (never files it).",
}


def compact_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for spec in specs:
        function = dict(spec["function"])
        function["description"] = COMPACT_DESCRIPTIONS[function["name"]]
        parameters = json.loads(json.dumps(function["parameters"]))
        for prop in parameters.get("properties", {}).values():
            prop.pop("description", None)
        function["parameters"] = parameters
        compact.append({"type": "function", "function": function})
    return compact


TOOL_SPECS: list[dict[str, Any]] = [
    search_policy.SPEC,
    get_claim_status.SPEC,
    draft_claim.SPEC,
]


def canonical_key(name: str, raw_arguments: str) -> tuple[str, str]:
    try:
        return name, json.dumps(parse_arguments(raw_arguments), sort_keys=True, ensure_ascii=False)
    except ValueError:
        return name, raw_arguments


def execute(name: str, raw_arguments: str, ctx: ToolContext) -> ToolOutcome:
    entry = TOOLS.get(name)
    if entry is None:
        known = ", ".join(sorted(TOOLS))
        return ToolOutcome(f"Unknown tool {name!r}. Available tools: {known}.", ok=False)
    model_cls, runner = entry
    try:
        args = model_cls.model_validate(parse_arguments(raw_arguments))
    except ValueError as exc:
        if isinstance(exc, ValidationError):
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                for e in exc.errors()
            )
        else:
            problems = str(exc)
        return ToolOutcome(f"Invalid arguments for {name}: {problems}", ok=False)
    with tool_call(name) as span:
        outcome = runner(args, ctx)
        span.set_attribute("tool.ok", outcome.ok)
        return outcome
