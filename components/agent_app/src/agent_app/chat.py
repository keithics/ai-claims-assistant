import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from agent_app.agent import AgentResult, run_agent
from agent_app.approval import ApprovalService
from agent_app.classify import classify
from agent_app.i18n import handoff_message, notice
from agent_app.llm import ChatClient, ModelError
from agent_app.prompts import build_messages
from agent_app.schemas import ChatRequest, ChatResponse, Citation, Route, Usage
from agent_app.tools import ClaimsGateway, ToolContext
from country_packs import CountryPack
from rag import PolicyDocument, RetrievedChunk, Retriever
from router import BudgetState, Intent, Risk, RouteDecision, RouteRequest, RoutingConfig, route
from shared import ModelPrice, cost_usd

ROUTE_REASON = "default deployment (router not enabled yet)"
_CITATION = re.compile(r"\[(\d{1,2})\]")


class RequestError(ValueError):
    pass


def _always_ok() -> BudgetState:
    return "ok"


@dataclass(frozen=True)
class ChatService:
    packs: Mapping[str, CountryPack]
    retriever: Retriever
    chat: ChatClient
    claims: ClaimsGateway
    approvals: ApprovalService
    deployment: str
    max_output_tokens: int
    prices: Mapping[str, ModelPrice]
    tiers: Mapping[str, str]
    max_steps: int = 6
    documents: Mapping[str, PolicyDocument] = field(default_factory=dict)
    routing: RoutingConfig | None = None
    budget_state: Callable[[], BudgetState] = _always_ok
    allow_tier_override: bool = False
    clock: Callable[[], float] = time.perf_counter

    def answer(self, request: ChatRequest) -> ChatResponse:
        pack = self.packs.get(request.country)
        if pack is None:
            raise RequestError(
                f"unknown country {request.country!r}; supported: {', '.join(sorted(self.packs))}"
            )
        if request.language not in pack.languages:
            raise RequestError(
                f"language {request.language!r} is not supported for {pack.code}; "
                f"supported: {', '.join(pack.languages)}"
            )
        if request.tier_override and not self.allow_tier_override:
            raise RequestError("tier_override is not enabled on this service")
        started = self.clock()
        intent, risk = classify(request.message, pack.code)
        decision = self._decide(request, pack, intent, risk)
        notice_text = notice(request.language, pack.human_handoff)
        conversation_id = request.conversation_id or uuid.uuid4().hex
        if decision.tier == "handoff":
            return ChatResponse(
                conversation_id=conversation_id,
                country=pack.code,
                language=request.language,
                answer=handoff_message(request.language, pack.human_handoff),
                citations=[],
                notice=notice_text,
                pending_approvals=[],
                usage=self._handoff_usage(decision, intent, risk, started),
            )
        history = [{"role": m.role, "content": m.content} for m in request.history]
        messages = build_messages(
            request.message, request.language, pack.name, history, pack.human_handoff
        )
        attempts = [decision.deployment or self.deployment, *decision.fallbacks]
        max_tokens = decision.max_output_tokens or self.max_output_tokens
        used = attempts[0]
        failure: ModelError | None = None
        result: AgentResult | None = None
        for used in attempts:
            try:
                result = run_agent(
                    chat=self.chat,
                    deployment=used,
                    messages=messages,
                    ctx=ToolContext(
                        country=pack.code,
                        language=request.language,
                        retriever=self.retriever,
                        claims=self.claims,
                    ),
                    max_steps=self.max_steps,
                    max_output_tokens=max_tokens,
                )
                break
            except ModelError as exc:
                failure = exc
        if result is None:
            raise failure or ModelError("no deployment available")
        return ChatResponse(
            conversation_id=conversation_id,
            country=pack.code,
            language=request.language,
            answer=result.answer,
            citations=cited(result.answer, result.sources),
            notice=notice_text,
            pending_approvals=[self.approvals.issue(draft) for draft in result.drafts],
            usage=self._usage(
                result,
                round((self.clock() - started) * 1000),
                used,
                decision,
                intent,
                risk,
                fallback_used=used != attempts[0],
            ),
        )

    def _decide(
        self, request: ChatRequest, pack: CountryPack, intent: Intent, risk: Risk
    ) -> RouteDecision:
        if self.routing is None:
            return RouteDecision(
                tier=self.tiers[self.deployment],  # type: ignore[arg-type]
                deployment=self.deployment,
                reason=ROUTE_REASON,
            )
        if request.tier_override:
            names = self.routing.deployments[request.tier_override]
            return RouteDecision(
                tier=request.tier_override,
                deployment=names[0],
                reason=f"tier forced to {request.tier_override} (evaluation override)",
                fallbacks=tuple(names[1:]),
                max_output_tokens=getattr(
                    self.routing.output_limits[intent], request.tier_override
                ),
            )
        route_request = RouteRequest(
            country=pack.code,
            language=request.language,
            intent=intent,
            risk=risk,
            allowed_tiers=tuple(pack.allowed_model_tiers),
        )
        return route(route_request, self.routing, self.budget_state())

    def _handoff_usage(
        self, decision: RouteDecision, intent: str, risk: str, started: float
    ) -> Usage:
        return Usage(
            route=Route(
                tier="handoff",
                reason=decision.reason,
                deployment="none",
                intent=intent,
                risk=risk,
            ),
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            cost_usd=0.0,
            latency_ms=round((self.clock() - started) * 1000),
            cache_hit=False,
            levers_fired=["handoff"],
            steps_used=0,
            loop_capped=False,
        )

    def _usage(
        self,
        result: AgentResult,
        latency_ms: int,
        deployment: str,
        decision: RouteDecision,
        intent: str,
        risk: str,
        *,
        fallback_used: bool,
    ) -> Usage:
        cost = sum(
            (
                cost_usd(deployment, c.input_tokens, c.cached_tokens, c.output_tokens, self.prices)
                for c in result.completions
            ),
            Decimal(0),
        )
        levers = ["routing"] if self.routing is not None else []
        if fallback_used:
            levers.append("fallback")
        return Usage(
            route=Route(
                tier=self.tiers[deployment],
                reason=decision.reason,
                deployment=deployment,
                intent=intent,
                risk=risk,
            ),
            input_tokens=sum(c.input_tokens for c in result.completions),
            output_tokens=sum(c.output_tokens for c in result.completions),
            cached_tokens=sum(c.cached_tokens for c in result.completions),
            cost_usd=float(cost),
            latency_ms=latency_ms,
            cache_hit=False,
            levers_fired=levers,
            steps_used=result.steps_used,
            loop_capped=result.loop_capped,
            tool_calls=[record.name for record in result.tool_calls],
            fallback_used=fallback_used,
        )


def cited(answer: str, sources: Sequence[RetrievedChunk]) -> list[Citation]:
    numbers = sorted({int(n) for n in _CITATION.findall(answer)})
    return [
        Citation(
            number=number,
            doc_id=sources[number - 1].doc_id,
            title=sources[number - 1].title,
            heading=sources[number - 1].heading,
            chunk_id=sources[number - 1].id,
            country=sources[number - 1].country,
        )
        for number in numbers
        if 1 <= number <= len(sources)
    ]
