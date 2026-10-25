from pydantic import BaseModel, ConfigDict, Field

from agent_app.prompts import DOC_CLOSE, DOC_OPEN, neutralize
from agent_app.tools.base import ToolContext, ToolOutcome


class SearchPolicyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)


SPEC = {
    "type": "function",
    "function": {
        "name": "search_policy",
        "description": "Search the policy documents for the user's country.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look up."}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def run(args: SearchPolicyArgs, ctx: ToolContext) -> ToolOutcome:
    chunks = ctx.retriever.retrieve(args.query, ctx.country, ctx.language)
    if not chunks:
        return ToolOutcome("No policy documents matched. Say so and offer a human agent.")
    blocks = []
    for chunk in chunks:
        number = ctx.source_number(chunk)
        header = f'{DOC_OPEN} number={number} title="{neutralize(chunk.title)}">>>'
        blocks.append(f"{header}\n{neutralize(chunk.text)}\n{DOC_CLOSE}")
    return ToolOutcome("\n\n".join(blocks))
