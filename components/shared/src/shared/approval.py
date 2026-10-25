import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass

MIN_KEY_LENGTH = 16
DRAFT_FIELDS = (
    "claim_id",
    "country",
    "claim_type",
    "incident_date",
    "description",
    "amount_claimed",
    "currency",
    "policy_number",
)


class TokenError(ValueError):
    pass


class TokenInvalidError(TokenError):
    pass


class TokenExpiredError(TokenError):
    pass


@dataclass(frozen=True)
class ApprovalToken:
    claim_id: str
    digest: str
    jti: str
    expires_at: int


def draft_digest(draft: Mapping[str, object]) -> str:
    selected = {name: draft.get(name) for name in DRAFT_FIELDS}
    canonical = json.dumps(
        selected, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key(secret: str | bytes) -> bytes:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    if len(key) < MIN_KEY_LENGTH:
        raise ValueError(f"signing key must be at least {MIN_KEY_LENGTH} bytes")
    return key


def _sign(key: bytes, body: str) -> str:
    return _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())


def issue_token(
    secret: str | bytes,
    *,
    claim_id: str,
    digest: str,
    ttl_seconds: int,
    now: float | None = None,
) -> str:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    issued = time.time() if now is None else now
    payload = {
        "v": 1,
        "cid": claim_id,
        "dig": digest,
        "jti": secrets.token_hex(8),
        "exp": int(issued) + ttl_seconds,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(_key(secret), body)}"


def verify_token(
    secret: str | bytes,
    token: str,
    *,
    claim_id: str,
    digest: str,
    now: float | None = None,
) -> ApprovalToken:
    parsed = peek_token(secret, token)
    current = time.time() if now is None else now
    if current >= parsed.expires_at:
        raise TokenExpiredError("approval token has expired")
    if parsed.claim_id != claim_id:
        raise TokenInvalidError("approval token is for a different claim")
    if not hmac.compare_digest(parsed.digest, digest):
        raise TokenInvalidError("the draft changed after the token was issued")
    return parsed


def peek_token(secret: str | bytes, token: str) -> ApprovalToken:
    key = _key(secret)
    body, dot, signature = token.partition(".")
    if not dot or not body or not signature:
        raise TokenInvalidError("malformed approval token")
    if not hmac.compare_digest(_sign(key, body), signature):
        raise TokenInvalidError("approval token signature does not match")
    try:
        payload = json.loads(_unb64(body))
        return ApprovalToken(
            claim_id=str(payload["cid"]),
            digest=str(payload["dig"]),
            jti=str(payload["jti"]),
            expires_at=int(payload["exp"]),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenInvalidError("approval token payload is unreadable") from exc
