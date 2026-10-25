import random
import re
import time
from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException, Response

from claims_api.chaos import Chaos
from claims_api.config import Settings
from claims_api.models import CLAIM_ID_PATTERN, Claim, DraftClaimRequest
from claims_api.store import ClaimStore
from shared import TokenError, TokenExpiredError, draft_digest, verify_token

_CLAIM_ID = re.compile(CLAIM_ID_PATTERN)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def digest_of(claim: Claim) -> str:
    return draft_digest(claim.model_dump(mode="json"))


def create_app(
    settings: Settings | None = None,
    *,
    chaos: Chaos | None = None,
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    config = settings or Settings.from_env()
    store = ClaimStore.from_seed_dir(config.seed_dir)
    injector = chaos or Chaos(
        config.latency_p50_ms,
        config.latency_p95_ms,
        config.failure_rate,
        rng=random.Random(config.random_seed),
    )
    used_tokens: set[str] = set()
    app = FastAPI(title="Kalayaan Mutual legacy claims system (mock)", version="0.1.0")

    async def flaky() -> None:
        if await injector.apply():
            raise _error(503, "unavailable", "legacy claims system is temporarily unavailable")

    def normalize(claim_id: str) -> str:
        normalized = claim_id.strip().upper()
        if not _CLAIM_ID.match(normalized):
            raise _error(422, "bad_claim_id", f"claim id must look like PH-1042, got {claim_id!r}")
        return normalized

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/claims/{claim_id}", response_model=Claim)
    async def get_claim(claim_id: str) -> Claim:
        await flaky()
        claim = store.get(normalize(claim_id))
        if claim is None:
            raise _error(404, "not_found", f"no claim {claim_id.upper()}")
        return claim

    @app.post("/claims", response_model=Claim, status_code=201)
    async def create_draft(request: DraftClaimRequest) -> Claim:
        await flaky()
        return store.create_draft(request)

    @app.post("/claims/{claim_id}/file", response_model=Claim)
    async def file_claim(
        claim_id: str,
        response: Response,
        x_approval_token: str | None = Header(default=None),
    ) -> Claim:
        await flaky()
        claim = store.get(normalize(claim_id))
        if claim is None:
            raise _error(404, "not_found", f"no claim {claim_id.upper()}")
        if not x_approval_token:
            raise _error(401, "approval_required", "an approval token is required to file a claim")
        if claim.status != "draft":
            raise _error(409, "not_a_draft", f"claim {claim.claim_id} is already {claim.status}")
        try:
            parsed = verify_token(
                config.signing_key,
                x_approval_token,
                claim_id=claim.claim_id,
                digest=digest_of(claim),
                now=clock(),
            )
        except TokenExpiredError as exc:
            raise _error(401, "token_expired", str(exc)) from exc
        except TokenError as exc:
            raise _error(401, "token_invalid", str(exc)) from exc
        if parsed.jti in used_tokens:
            raise _error(401, "token_used", "this approval token was already used")
        used_tokens.add(parsed.jti)
        return store.file(claim.claim_id)

    return app
