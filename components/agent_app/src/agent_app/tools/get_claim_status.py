import json

from pydantic import BaseModel, ConfigDict, Field

from agent_app.tools.base import ToolContext, ToolOutcome
from agent_app.tools.claims_client import ClaimsApiError

STATUS_FIELDS = (
    "claim_id",
    "claim_type",
    "status",
    "incident_date",
    "amount_claimed",
    "currency",
    "last_update",
)


class ClaimStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^[A-Za-z]{2}-\d{3,6}$")


SPEC = {
    "type": "function",
    "function": {
        "name": "get_claim_status",
        "description": "Look up the status of an existing claim by its claim number, like PH-1042.",
        "parameters": {
            "type": "object",
            "properties": {"claim_id": {"type": "string", "description": "For example PH-1042."}},
            "required": ["claim_id"],
            "additionalProperties": False,
        },
    },
}


def run(args: ClaimStatusArgs, ctx: ToolContext) -> ToolOutcome:
    claim_id = args.claim_id.upper()
    if not claim_id.startswith(f"{ctx.country.upper()}-"):
        return ToolOutcome(
            f"Claims for other countries cannot be looked up here. Only {ctx.country.upper()}-"
            "numbers are available. Tell the user.",
            ok=False,
        )
    try:
        claim = ctx.claims.get_claim(claim_id)
    except ClaimsApiError as exc:
        if exc.kind == "not_found":
            return ToolOutcome(
                f"No claim {claim_id} exists. Ask the user to check the number.", ok=False
            )
        if exc.kind == "unavailable":
            return ToolOutcome(
                "The claims system is not responding right now. Tell the user to try again "
                "shortly or ask for a human agent.",
                ok=False,
            )
        return ToolOutcome(f"The claims system refused the request: {exc}", ok=False)
    summary = {name: claim.get(name) for name in STATUS_FIELDS}
    return ToolOutcome(json.dumps(summary, ensure_ascii=False))
