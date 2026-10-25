from dataclasses import dataclass, field
from typing import Any, Literal

from agent_app.i18n import CANNOT_FINISH
from agent_app.llm import ChatClient, Completion, Message, assistant_message
from agent_app.tools import TOOL_SPECS, ToolContext, canonical_key, execute
from rag import RetrievedChunk

Outcome = Literal["answered", "loop_capped", "loop_detected", "empty_answer"]


@dataclass(frozen=True)
class ToolRecord:
    name: str
    ok: bool


@dataclass
class AgentResult:
    answer: str
    outcome: Outcome
    completions: list[Completion]
    sources: list[RetrievedChunk]
    drafts: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolRecord] = field(default_factory=list)

    @property
    def steps_used(self) -> int:
        return len(self.completions)

    @property
    def loop_capped(self) -> bool:
        return self.outcome == "loop_capped"

    @property
    def loop_detected(self) -> bool:
        return self.outcome == "loop_detected"


def run_agent(
    *,
    chat: ChatClient,
    deployment: str,
    messages: list[Message],
    ctx: ToolContext,
    max_steps: int,
    max_output_tokens: int,
) -> AgentResult:
    conversation = list(messages)
    completions: list[Completion] = []
    records: list[ToolRecord] = []
    drafts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    safe = CANNOT_FINISH[ctx.language]

    def finish(answer: str, outcome: Outcome) -> AgentResult:
        return AgentResult(answer, outcome, completions, list(ctx.sources), drafts, records)

    for _ in range(max_steps):
        completion = chat.complete(
            conversation,
            deployment=deployment,
            country=ctx.country,
            max_output_tokens=max_output_tokens,
            tools=TOOL_SPECS,
        )
        completions.append(completion)
        if not completion.tool_calls:
            text = completion.text.strip()
            return finish(text, "answered") if text else finish(safe, "empty_answer")
        conversation.append(assistant_message(completion))
        for call in completion.tool_calls:
            key = canonical_key(call.name, call.arguments)
            if key in seen:
                return finish(safe, "loop_detected")
            seen.add(key)
            outcome = execute(call.name, call.arguments, ctx)
            records.append(ToolRecord(call.name, outcome.ok))
            if outcome.draft is not None:
                drafts.append(outcome.draft)
            conversation.append(
                {"role": "tool", "tool_call_id": call.id, "content": outcome.model_text}
            )
    return finish(safe, "loop_capped")
