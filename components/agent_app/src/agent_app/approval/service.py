import time
from collections.abc import Callable
from typing import Any

from agent_app.schemas import ClaimView, PendingApproval
from agent_app.tools.claims_client import ClaimsApiError, ClaimsFiler, ClaimsGateway
from shared import (
    TokenExpiredError,
    TokenInvalidError,
    draft_digest,
    issue_token,
    peek_token,
    verify_token,
)


class ApprovalError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class ApprovalService:
    def __init__(
        self,
        claims: ClaimsGateway,
        filer: ClaimsFiler,
        signing_key: str,
        ttl_seconds: int = 900,
        clock: Callable[[], float] = time.time,
    ) -> None:
        issue_token(signing_key, claim_id="X-000", digest="d", ttl_seconds=1)
        self._claims = claims
        self._filer = filer
        self._key = signing_key
        self._ttl = ttl_seconds
        self._clock = clock
        self._used: set[str] = set()

    def issue(self, draft: dict[str, Any]) -> PendingApproval:
        now = self._clock()
        token = issue_token(
            self._key,
            claim_id=str(draft["claim_id"]),
            digest=draft_digest(draft),
            ttl_seconds=self._ttl,
            now=now,
        )
        return PendingApproval(
            claim_id=str(draft["claim_id"]),
            token=token,
            expires_at=int(now) + self._ttl,
            draft=ClaimView.from_claim(draft),
        )

    def approve(self, claim_id: str, token: str) -> ClaimView:
        claim_id = claim_id.upper()
        try:
            current = self._claims.get_claim(claim_id)
        except ClaimsApiError as exc:
            raise _from_claims(exc) from exc
        try:
            parsed = verify_token(
                self._key,
                token,
                claim_id=claim_id,
                digest=draft_digest(current),
                now=self._clock(),
            )
        except TokenExpiredError as exc:
            raise ApprovalError(410, "token_expired", str(exc)) from exc
        except TokenInvalidError as exc:
            raise ApprovalError(400, "token_invalid", str(exc)) from exc
        if parsed.jti in self._used:
            raise ApprovalError(409, "token_used", "this approval was already used")
        try:
            filed = self._filer.file_claim(claim_id, token)
        except ClaimsApiError as exc:
            raise _from_claims(exc) from exc
        self._used.add(parsed.jti)
        return ClaimView.from_claim(filed)

    def reject(self, claim_id: str, token: str) -> str:
        claim_id = claim_id.upper()
        try:
            parsed = peek_token(self._key, token)
        except TokenInvalidError as exc:
            raise ApprovalError(400, "token_invalid", str(exc)) from exc
        if parsed.claim_id != claim_id:
            raise ApprovalError(400, "token_invalid", "approval token is for a different claim")
        self._used.add(parsed.jti)
        return claim_id


def _from_claims(exc: ClaimsApiError) -> ApprovalError:
    if exc.kind == "not_found":
        return ApprovalError(404, "not_found", str(exc))
    if exc.kind == "unavailable":
        return ApprovalError(503, "unavailable", str(exc))
    return ApprovalError(409, "claim_rejected", str(exc))
