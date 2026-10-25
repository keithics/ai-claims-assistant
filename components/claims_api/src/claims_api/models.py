from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimType = Literal["motor", "health", "home"]
ClaimStatus = Literal["draft", "submitted", "under_review", "approved", "paid", "rejected"]

CLAIM_ID_PATTERN = r"^[A-Z]{2}-\d{3,6}$"


class Claim(BaseModel):
    claim_id: str
    country: str
    policy_number: str | None = None
    claim_type: ClaimType
    incident_date: date
    description: str
    amount_claimed: Decimal | None = None
    currency: str
    status: ClaimStatus
    last_update: date | None = None
    filed_at: str | None = None


class DraftClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str = Field(pattern=r"^[a-z]{2}$")
    claim_type: ClaimType
    incident_date: date
    description: str = Field(min_length=1, max_length=1000)
    amount_claimed: Decimal | None = Field(default=None, ge=0)
    policy_number: str | None = Field(default=None, pattern=r"^POL-[A-Z]{2}-\d{5,12}$")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
