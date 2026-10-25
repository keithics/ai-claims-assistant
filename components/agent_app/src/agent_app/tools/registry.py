import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from agent_app.llm import parse_arguments
from agent_app.tools import draft_claim, get_claim_status, search_policy
from agent_app.tools.base import ToolContext, ToolOutcome

Runner = Callable[[Any, ToolContext], ToolOutcome]

TOOLS: dict[str, tuple[type[BaseModel], Runner]] = {
    "search_policy": (search_policy.SearchPolicyArgs, search_policy.run),
    "get_claim_status": (get_claim_status.ClaimStatusArgs, get_claim_status.run),
    "draft_claim": (draft_claim.DraftClaimArgs, draft_claim.run),
}

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
    return runner(args, ctx)
