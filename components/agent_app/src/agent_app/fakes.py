import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from agent_app.approval import ApprovalService
from agent_app.chat import ChatService
from agent_app.config import Settings
from agent_app.llm import Completion, Message, ToolCall
from agent_app.routing import load_routing
from agent_app.tools import ClaimsClient, RestrictedClaims
from country_packs import load_country_packs, load_model_catalog, prices_from_catalog
from rag import Retriever, chunk_markdown, load_policy_documents

FAKE_MODE_ENV = "AGENT_FAKE_MODE"

_CLAIM_ID = re.compile(r"\b([A-Za-z]{2}-\d{3,6})\b")
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:php|sgd|idr|thb|jpy|usd)\b", re.IGNORECASE)
_WORDS = re.compile(r"\w+", re.UNICODE)


class KeywordBackend:
    def __init__(self) -> None:
        packs = load_country_packs()
        self._rows: list[dict[str, Any]] = []
        for doc in load_policy_documents(packs=packs):
            for chunk in chunk_markdown(doc.body, max_tokens=200, overlap_tokens=20):
                self._rows.append(
                    {
                        "id": f"{doc.doc_id}-{chunk.index:03d}",
                        "country": doc.country,
                        "language": doc.language,
                        "doc_id": doc.doc_id,
                        "title": doc.title,
                        "heading": chunk.heading,
                        "content": chunk.text,
                        "chunk_index": chunk.index,
                    }
                )

    def search(
        self,
        *,
        text: str,
        vector: Sequence[float],
        filter: str,
        top: int,
        select: Sequence[str],
        search_fields: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        match = re.search(r"'(\w+)'", filter)
        country = match.group(1) if match else ""
        wanted = set(_WORDS.findall(text.lower()))
        scored = []
        for row in self._rows:
            if row["country"] != country:
                continue
            overlap = len(wanted & set(_WORDS.findall(row["content"].lower())))
            scored.append((overlap, row))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        return [{**row, "@search.score": float(score)} for score, row in scored[:top]]


def _embed(texts: Sequence[str], *, country: str) -> list[list[float]]:
    return [[0.0] for _ in texts]


class RuleBasedChat:
    def complete(
        self,
        messages: Sequence[Message],
        *,
        deployment: str,
        country: str,
        max_output_tokens: int,
        tools: Sequence[dict[str, Any]] | None = None,
        cache_key: str | None = None,
        intent: str | None = None,
    ) -> Completion:
        size = len(json.dumps(list(messages), default=str))
        last = messages[-1]
        if last["role"] == "tool":
            return Completion(self._answer_from_tool(str(last["content"])), size // 4, 40, 0)
        question = str(last["content"]).split("MESSAGE:\n", 1)[-1]
        call = self._plan(question)
        if call is None:
            reply = (
                "Please tell me the claim type, the date it happened (YYYY-MM-DD) "
                "and what happened, and I will prepare a draft for you."
            )
            return Completion(reply, size // 4, 30, 0)
        return Completion("", size // 4, 15, 0, (call,))

    @staticmethod
    def _plan(question: str) -> ToolCall | None:
        lowered = question.lower()
        claim = _CLAIM_ID.search(question)
        if claim and "status" in lowered:
            return ToolCall("call-1", "get_claim_status", json.dumps({"claim_id": claim.group(1)}))
        wants_to_file = any(word in lowered for word in ("file a claim", "file it", "draft"))
        if wants_to_file or (_DATE.search(question) and "claim" in lowered):
            date = _DATE.search(question)
            if date is None:
                return None
            kind = "motor"
            if any(word in lowered for word in ("hospital", "doctor", "health")):
                kind = "health"
            elif any(word in lowered for word in ("home", "house", "roof")):
                kind = "home"
            arguments: dict[str, Any] = {
                "claim_type": kind,
                "incident_date": date.group(1),
                "description": question.strip()[:300],
            }
            amount = _AMOUNT.search(question)
            if amount:
                arguments["amount_claimed"] = float(amount.group(1).replace(",", ""))
            return ToolCall("call-1", "draft_claim", json.dumps(arguments))
        return ToolCall("call-1", "search_policy", json.dumps({"query": question}))

    @staticmethod
    def _answer_from_tool(content: str) -> str:
        try:
            data = json.loads(content)
        except ValueError:
            data = None
        if isinstance(data, dict) and "next_step" in data:
            return (
                f"Your draft {data['claim_id']} is ready. "
                "Please review it and approve it on the approval screen."
            )
        if isinstance(data, dict) and "status" in data:
            return f"Claim {data['claim_id']} is {data['status'].replace('_', ' ')}."
        if "<<<DOCUMENT" in content:
            body = content.split(">>>", 1)[1].strip().splitlines()
            text = next((line for line in body if line and not line.startswith("#")), "")
            return f"{text.lstrip('- ').strip()} [1]"
        return "I could not complete that. I can connect you with a human agent."


def build_fake_service(settings: Settings) -> ChatService:
    packs = load_country_packs()
    catalog = load_model_catalog()
    client = ClaimsClient(settings.claims_api_url, attempts=2, backoff_seconds=0.05)
    restricted = RestrictedClaims(client)
    return ChatService(
        packs=packs,
        retriever=Retriever(KeywordBackend(), _embed, packs, top_k=settings.top_k),
        chat=RuleBasedChat(),
        claims=restricted,
        approvals=ApprovalService(
            restricted,
            client,
            settings.approval_signing_key,
            ttl_seconds=settings.approval_ttl_seconds,
        ),
        deployment=settings.chat_deployment,
        max_output_tokens=settings.max_output_tokens,
        prices=prices_from_catalog(catalog),
        tiers={name: d.tier for name, d in catalog.deployments.items()},
        max_steps=settings.max_steps,
        documents={d.doc_id: d for d in load_policy_documents(packs=packs)},
        routing=load_routing(settings.routing_path, catalog.deployments),
        allow_tier_override=settings.allow_tier_override,
    )
