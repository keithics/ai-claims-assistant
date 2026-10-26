import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from opentelemetry.trace import Span

from agent_app.agent import AgentResult, run_agent
from agent_app.approval import ApprovalService
from agent_app.classify import classify
from agent_app.i18n import (
    filtered_message,
    handoff_message,
    notice,
    out_of_scope_message,
    self_harm_message,
)
from agent_app.levers import UnknownLeverError, parse_levers
from agent_app.llm import ChatClient, ContentFilteredError, ModelError
from agent_app.prompts import CONCISE_HINTS, build_messages, cap_history
from agent_app.safety import is_self_harm
from agent_app.schemas import ChatRequest, ChatResponse, Citation, Route, Usage
from agent_app.scope import ScopeGuard
from agent_app.tools import TOOL_SPECS, ClaimsGateway, ToolContext, compact_specs
from country_packs import CountryPack
from rag import PolicyDocument, RetrievedChunk, Retriever
from router import BudgetState, Intent, Risk, RouteDecision, RouteRequest, RoutingConfig, route
from shared import ModelPrice, cost_usd
from telemetry import chat_turn, content_for_logging, mark_error, record_route, set_attributes

ROUTE_REASON = "default deployment (router not enabled yet)"
_CITATION = re.compile(r"\[(\d{1,2})\]")


class RequestError(ValueError):
    pass


def _always_ok(country: str) -> BudgetState:
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
    budget_state: Callable[[str], BudgetState] = _always_ok
    allow_tier_override: bool = False
    env: str = "unknown"
    levers: frozenset[str] = frozenset()
    scope: ScopeGuard | None = None
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
        conversation_id = request.conversation_id or uuid.uuid4().hex
        with chat_turn(
            conversation_id=conversation_id,
            country=pack.code,
            language=request.language,
            env=self.env,
        ) as span:
            return self._answer(request, pack, conversation_id, span)

    def _answer(
        self, request: ChatRequest, pack: CountryPack, conversation_id: str, span: Span
    ) -> ChatResponse:
        started = self.clock()
        if is_self_harm(request.message):
            return self._stop(
                request,
                pack,
                conversation_id,
                span,
                answer=self_harm_message(request.language, pack.human_handoff),
                lever="self_harm_response",
                reason="the message suggests self-harm: fixed caring reply, no model call",
                started=started,
            )
        if self.scope is not None:
            outside, score = self.scope.out_of_scope(
                request.message, pack.code, has_history=bool(request.history)
            )
            if score is not None:
                set_attributes(span, {"scope_score": round(score, 4)})
            if outside:
                return self._stop(
                    request,
                    pack,
                    conversation_id,
                    span,
                    answer=out_of_scope_message(request.language, pack.name, pack.human_handoff),
                    lever="scope_guard",
                    reason=f"closer to off-topic requests than to claims (margin {score:.2f})",
                    started=started,
                )
        intent, risk = classify(request.message, pack.code)
        decision = self._decide(request, pack, intent, risk)
        record_route(
            decision=decision.tier,
            reason=decision.reason,
            deployment=decision.deployment,
            intent=intent,
            risk=risk,
        )
        notice_text = notice(request.language, pack.human_handoff)
        if decision.tier == "handoff":
            set_attributes(span, {"outcome": "handoff", "cost_usd": 0.0, "steps_used": 0})
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
        levers = self._levers(request)
        fired: set[str] = set()
        history = [{"role": m.role, "content": m.content} for m in request.history]
        if "history_cap" in levers:
            capped = cap_history(history)
            if capped != history:
                fired.add("history_cap")
            history = capped
        messages = build_messages(
            request.message,
            request.language,
            pack.name,
            history,
            pack.human_handoff,
            compact="compact_prompts" in levers,
            style=CONCISE_HINTS[intent] if "concise_style" in levers else None,
        )
        fired |= levers & {"compact_prompts", "concise_style"}
        attempts = [decision.deployment or self.deployment, *decision.fallbacks]
        max_tokens = self._max_tokens(decision, levers, fired)
        used = attempts[0]
        failure: ModelError | None = None
        result: AgentResult | None = None
        for used in attempts:
            ctx = ToolContext(
                country=pack.code,
                language=request.language,
                retriever=self.retriever,
                claims=self.claims,
                levers=levers,
            )
            try:
                result = run_agent(
                    chat=self.chat,
                    deployment=used,
                    messages=messages,
                    ctx=ctx,
                    max_steps=self.max_steps,
                    max_output_tokens=max_tokens,
                    tools=compact_specs(TOOL_SPECS) if "compact_prompts" in levers else None,
                    intent=cache_intent(intent, risk, bool(request.history)),
                    language=request.language,
                    cache_key=(
                        f"{pack.code}:{request.language}" if "prompt_cache_key" in levers else None
                    ),
                    prompt_content=content_for_logging(
                        request.message, env=self.env, log_prompts=pack.log_prompts
                    ),
                )
                break
            except ContentFilteredError:
                set_attributes(span, {"outcome": "content_filtered", "content_filtered": True})
                return ChatResponse(
                    conversation_id=conversation_id,
                    country=pack.code,
                    language=request.language,
                    answer=filtered_message(request.language, pack.human_handoff),
                    citations=[],
                    notice=notice_text,
                    pending_approvals=[],
                    usage=self._handoff_usage(
                        decision, intent, risk, started, tier="filtered", lever="content_filter"
                    ),
                )
            except ModelError as exc:
                failure = exc
        if result is None:
            error = failure or ModelError("no deployment available")
            set_attributes(span, {"outcome": "model_error", "fallback_used": len(attempts) > 1})
            mark_error(span, error)
            raise error
        usage = self._usage(
            result,
            round((self.clock() - started) * 1000),
            used,
            decision,
            intent,
            risk,
            fallback_used=used != attempts[0],
            fired=fired | ctx.fired,
            levers=levers,
        )
        set_attributes(
            span,
            {
                "outcome": result.outcome,
                "steps_used": usage.steps_used,
                "loop_capped": usage.loop_capped,
                "cost_usd": usage.cost_usd,
                "fallback_used": usage.fallback_used,
                "cache_hit": usage.cache_hit,
                "route_tier": usage.route.tier,
                "gen_ai.request.model": used,
                "gen_ai.usage.input_tokens": usage.input_tokens,
                "gen_ai.usage.output_tokens": usage.output_tokens,
            },
        )
        return ChatResponse(
            conversation_id=conversation_id,
            country=pack.code,
            language=request.language,
            answer=result.answer,
            citations=cited(result.answer, result.sources),
            notice=notice_text,
            pending_approvals=[self.approvals.issue(draft) for draft in result.drafts],
            usage=usage,
        )

    def _stop(
        self,
        request: ChatRequest,
        pack: CountryPack,
        conversation_id: str,
        span: Span,
        *,
        answer: str,
        lever: str,
        reason: str,
        started: float,
    ) -> ChatResponse:
        set_attributes(
            span, {"outcome": lever, "cost_usd": 0.0, "steps_used": 0, "route_tier": lever}
        )
        return ChatResponse(
            conversation_id=conversation_id,
            country=pack.code,
            language=request.language,
            answer=answer,
            citations=[],
            notice=notice(request.language, pack.human_handoff),
            pending_approvals=[],
            usage=Usage(
                route=Route(
                    tier=lever, reason=reason, deployment="none", intent="other", risk="low"
                ),
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                cost_usd=0.0,
                latency_ms=round((self.clock() - started) * 1000),
                cache_hit=False,
                levers_fired=[lever],
                steps_used=0,
                loop_capped=False,
            ),
        )

    def _levers(self, request: ChatRequest) -> frozenset[str]:
        if request.levers is None:
            return self.levers
        if not self.allow_tier_override:
            raise RequestError("levers can only be chosen per request when overrides are enabled")
        try:
            return parse_levers(request.levers)
        except UnknownLeverError as exc:
            raise RequestError(str(exc)) from exc

    def _max_tokens(self, decision: RouteDecision, levers: frozenset[str], fired: set[str]) -> int:
        if "output_limits" in levers and decision.max_output_tokens:
            fired.add("output_limits")
            return decision.max_output_tokens
        if decision.tier == "large" and decision.max_output_tokens:
            return decision.max_output_tokens
        return self.max_output_tokens

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
        return route(route_request, self.routing, self.budget_state(pack.code))

    def _handoff_usage(
        self,
        decision: RouteDecision,
        intent: str,
        risk: str,
        started: float,
        *,
        tier: str = "handoff",
        lever: str = "handoff",
    ) -> Usage:
        return Usage(
            route=Route(
                tier=tier,
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
            levers_fired=[lever],
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
        fired: set[str] | None = None,
        levers: frozenset[str] = frozenset(),
    ) -> Usage:
        cost = sum(
            (
                cost_usd(deployment, c.input_tokens, c.cached_tokens, c.output_tokens, self.prices)
                for c in result.completions
            ),
            Decimal(0),
        )
        levers_fired = ["routing"] if self.routing is not None else []
        levers_fired += sorted(fired or ())
        if "prompt_cache_key" in levers and sum(c.cached_tokens for c in result.completions) > 0:
            levers_fired.append("prompt_cache_key")
        if fallback_used:
            levers_fired.append("fallback")
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
            levers_fired=levers_fired,
            steps_used=result.steps_used,
            loop_capped=result.loop_capped,
            tool_calls=[record.name for record in result.tool_calls],
            fallback_used=fallback_used,
        )


def cache_intent(intent: str, risk: str, has_history: bool) -> str | None:
    """Only a plain, low-risk FAQ with no client-supplied history may be answered from the cache."""
    return "faq" if intent == "faq" and risk == "low" and not has_history else None


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
