import json
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_app.tools.base import ToolContext, ToolOutcome
from agent_app.tools.claims_client import ClaimsApiError


class DraftClaimArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: Literal["motor", "health", "home"]
    incident_date: date
    description: str = Field(min_length=1, max_length=1000)
    amount_claimed: Decimal | None = Field(default=None, ge=0)
    policy_number: str | None = Field(default=None, pattern=r"^POL-[A-Z]{2}-\d{5,12}$")


SPEC = {
    "type": "function",
    "function": {
        "name": "draft_claim",
        "description": (
            "Prepare a claim draft for the user to review and approve. It does not file the claim. "
            "Call it as soon as you have claim_type, incident_date and description. "
            "amount_claimed and policy_number are optional: do not ask the user for them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string", "enum": ["motor", "health", "home"]},
                "incident_date": {"type": "string", "description": "YYYY-MM-DD"},
                "description": {"type": "string", "description": "What happened."},
                "amount_claimed": {"type": "number", "description": "Optional amount."},
                "policy_number": {
                    "type": "string",
                    "description": "Optional, like POL-PH-1234567.",
                },
            },
            "required": ["claim_type", "incident_date", "description"],
            "additionalProperties": False,
        },
    },
}


def run(args: DraftClaimArgs, ctx: ToolContext) -> ToolOutcome:
    request = args.model_dump(mode="json", exclude_none=True)
    request["country"] = ctx.country
    try:
        draft = ctx.claims.create_draft(request)
    except ClaimsApiError as exc:
        if exc.kind == "unavailable":
            return ToolOutcome(
                "The claims system is not responding, so no draft was created. Tell the user "
                "to try again shortly or ask for a human agent.",
                ok=False,
            )
        return ToolOutcome(f"The draft was refused: {exc}", ok=False)
    visible = {k: draft.get(k) for k in ("claim_id", "claim_type", "incident_date", "status")}
    visible["next_step"] = (
        "Draft created. Tell the user to review it and approve it on the approval screen. "
        "You cannot file or approve it."
    )
    return ToolOutcome(json.dumps(visible, ensure_ascii=False), draft=draft)
