import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from agent_app import Completion
from agent_app.llm import ToolCall
from agent_app.tools import ClaimsApiError
from country_packs import load_country_packs, load_model_catalog, prices_from_catalog
from rag import chunk_markdown, load_policy_documents

PACKS = load_country_packs()


def catalog_args() -> dict[str, Any]:
    catalog = load_model_catalog()
    return {
        "prices": prices_from_catalog(catalog),
        "tiers": {n: d.tier for n, d in catalog.deployments.items()},
    }


class PolicyBackend:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []
        for doc in load_policy_documents(packs=PACKS):
            for chunk in chunk_markdown(doc.body, max_tokens=200, overlap_tokens=20):
                self.rows.append(
                    {
                        "id": f"{doc.doc_id}-{chunk.index:03d}",
                        "country": doc.country,
                        "language": doc.language,
                        "doc_id": doc.doc_id,
                        "title": doc.title,
                        "heading": chunk.heading,
                        "content": chunk.text,
                        "chunk_index": chunk.index,
                        "@search.score": 1.0,
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
        self.calls.append({"filter": filter, "text": text})
        country = re.search(r"'(\w+)'", filter)
        assert country is not None
        mine = [r for r in self.rows if r["country"] == country.group(1)]
        order = {"deadlines": 0, "overview": 1}
        wanted = [
            r
            for r in mine
            if not r["doc_id"].endswith("-fil") and r["doc_id"].split("-", 1)[1] in order
        ]
        wanted.sort(key=lambda r: (order[r["doc_id"].split("-", 1)[1]], r["chunk_index"]))
        return wanted[:top]


def call(name: str, arguments: Mapping[str, Any] | str, call_id: str = "c1") -> ToolCall:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return ToolCall(call_id, name, raw)


def say(text: str, input_tokens: int = 100, output_tokens: int = 20) -> Completion:
    return Completion(text, input_tokens, output_tokens, 0)


def use(*calls: ToolCall, input_tokens: int = 100, output_tokens: int = 10) -> Completion:
    return Completion("", input_tokens, output_tokens, 0, tuple(calls))


class ScriptedChat:
    def __init__(self, script: Sequence[Completion | Exception] | None = None) -> None:
        self.script = list(script) if script is not None else None
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        deployment: str,
        country: str,
        max_output_tokens: int,
        tools: Sequence[dict[str, Any]] | None = None,
        cache_key: str | None = None,
        intent: str | None = None,
    ) -> Completion:
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "deployment": deployment,
                "country": country,
                "max": max_output_tokens,
                "tools": tools,
                "cache_key": cache_key,
                "intent": intent,
            }
        )
        if self.script is not None:
            assert self.script, "the model was called more often than the test scripted"
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        last = messages[-1]
        if last["role"] == "tool":
            number = re.search(r"\*\*(\d+)", str(last["content"]))
            if number:
                return say(f"The deadline is {number.group(1)} days [1].")
            return say("I could not find that in the documents.")
        question = str(last["content"]).split("MESSAGE:\n", 1)[1]
        return use(call("search_policy", {"query": question}))


class FakeClaims:
    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.lookups: list[str] = []
        self.drafts: list[dict[str, Any]] = []
        self.claims = {
            "PH-1042": {
                "claim_id": "PH-1042",
                "claim_type": "motor",
                "status": "under_review",
                "incident_date": "2026-09-12",
                "amount_claimed": "15000",
                "currency": "PHP",
                "last_update": "2026-10-11",
                "policy_number": "POL-PH-1207294",
                "description": "internal detail",
            }
        }

    def get_claim(self, claim_id: str) -> dict[str, Any]:
        self.lookups.append(claim_id)
        if self.unavailable:
            raise ClaimsApiError("unavailable", "claims system is temporarily unavailable")
        if claim_id not in self.claims:
            raise ClaimsApiError("not_found", f"no claim {claim_id}")
        return self.claims[claim_id]

    def create_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        if self.unavailable:
            raise ClaimsApiError("unavailable", "claims system is temporarily unavailable")
        self.drafts.append(draft)
        claim = {
            "claim_id": f"{draft['country'].upper()}-{5000 + len(self.drafts)}",
            "country": draft["country"],
            "claim_type": draft["claim_type"],
            "incident_date": draft["incident_date"],
            "description": draft["description"],
            "amount_claimed": (
                None if draft.get("amount_claimed") is None else str(draft["amount_claimed"])
            ),
            "currency": "PHP",
            "policy_number": draft.get("policy_number"),
            "status": "draft",
        }
        self.claims[claim["claim_id"]] = claim
        return dict(claim)


class FakeFiler:
    def __init__(self, claims: FakeClaims) -> None:
        self.claims = claims
        self.filed: list[tuple[str, str]] = []
        self.error: ClaimsApiError | None = None

    def file_claim(self, claim_id: str, token: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        self.filed.append((claim_id, token))
        claim = self.claims.claims[claim_id]
        claim["status"] = "submitted"
        claim["filed_at"] = "2026-10-25T10:00:00+00:00"
        return dict(claim)
