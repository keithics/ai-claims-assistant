import json
from datetime import UTC, date, datetime
from pathlib import Path

from claims_api.config import CURRENCIES
from claims_api.models import Claim, DraftClaimRequest

FIRST_DRAFT_NUMBER = 5001


class ClaimStore:
    def __init__(self, claims: list[Claim]) -> None:
        self._claims = {c.claim_id: c for c in claims}
        self._next: dict[str, int] = {}

    @classmethod
    def from_seed_dir(cls, seed_dir: Path) -> "ClaimStore":
        files = sorted(seed_dir.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"no seed files (*.json) in {seed_dir}")
        claims = [
            Claim.model_validate(item)
            for file in files
            for item in json.loads(file.read_text(encoding="utf-8"))["claims"]
        ]
        return cls(claims)

    def get(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def countries(self) -> list[str]:
        return sorted({c.country for c in self._claims.values()})

    def create_draft(self, request: DraftClaimRequest) -> Claim:
        number = self._next.get(request.country, FIRST_DRAFT_NUMBER)
        self._next[request.country] = number + 1
        claim = Claim(
            claim_id=f"{request.country.upper()}-{number}",
            country=request.country,
            policy_number=request.policy_number,
            claim_type=request.claim_type,
            incident_date=request.incident_date,
            description=request.description,
            amount_claimed=request.amount_claimed,
            currency=request.currency or CURRENCIES.get(request.country, "USD"),
            status="draft",
            last_update=date.today(),
        )
        self._claims[claim.claim_id] = claim
        return claim

    def file(self, claim_id: str) -> Claim:
        claim = self._claims[claim_id]
        filed = claim.model_copy(
            update={
                "status": "submitted",
                "last_update": date.today(),
                "filed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        self._claims[claim_id] = filed
        return filed
