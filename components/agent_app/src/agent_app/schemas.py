from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    country: str = Field(min_length=2, max_length=2)
    language: str = Field(min_length=2, max_length=3)
    conversation_id: str | None = Field(default=None, max_length=64)
    tier_override: Literal["small", "large"] | None = None
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


class Citation(BaseModel):
    number: int
    doc_id: str
    title: str
    heading: str
    chunk_id: str
    country: str


class ClaimView(BaseModel):
    claim_id: str
    country: str
    claim_type: str
    incident_date: str
    description: str
    amount_claimed: str | None = None
    currency: str
    policy_number: str | None = None
    status: str
    filed_at: str | None = None

    @classmethod
    def from_claim(cls, claim: dict[str, Any]) -> "ClaimView":
        return cls(
            claim_id=claim["claim_id"],
            country=claim["country"],
            claim_type=claim["claim_type"],
            incident_date=str(claim["incident_date"]),
            description=claim["description"],
            amount_claimed=(
                None if claim.get("amount_claimed") is None else str(claim["amount_claimed"])
            ),
            currency=claim["currency"],
            policy_number=claim.get("policy_number"),
            status=claim["status"],
            filed_at=claim.get("filed_at"),
        )


class PendingApproval(BaseModel):
    claim_id: str
    token: str
    expires_at: int
    draft: ClaimView


class Route(BaseModel):
    tier: str
    reason: str
    deployment: str
    intent: str = "other"
    risk: str = "low"


class Usage(BaseModel):
    route: Route
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: int
    cache_hit: bool
    levers_fired: list[str]
    steps_used: int
    loop_capped: bool
    tool_calls: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class CountryInfo(BaseModel):
    code: str
    name: str
    languages: list[str]


class DocumentView(BaseModel):
    doc_id: str
    title: str
    country: str
    language: str
    body: str


class ChatResponse(BaseModel):
    conversation_id: str
    country: str
    language: str
    answer: str
    citations: list[Citation]
    notice: str
    pending_approvals: list[PendingApproval] = Field(default_factory=list)
    usage: Usage


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^[A-Za-z]{2}-\d{3,6}$")
    token: str = Field(min_length=10, max_length=2000)


class ApproveResponse(BaseModel):
    status: Literal["filed"]
    claim: ClaimView


class RejectResponse(BaseModel):
    status: Literal["rejected_by_user"]
    claim_id: str
