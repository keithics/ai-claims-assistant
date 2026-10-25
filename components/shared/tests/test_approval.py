import pytest

from shared import (
    TokenExpiredError,
    TokenInvalidError,
    draft_digest,
    issue_token,
    peek_token,
    verify_token,
)

KEY = "k" * 32
DRAFT = {
    "claim_id": "PH-5001",
    "country": "ph",
    "claim_type": "motor",
    "incident_date": "2026-10-01",
    "description": "Rear-ended at a junction",
    "amount_claimed": "12000.00",
    "currency": "PHP",
    "policy_number": None,
}
DIGEST = draft_digest(DRAFT)


def token(now: float = 1000.0, ttl: int = 900, **overrides: str) -> str:
    args = {"claim_id": "PH-5001", "digest": DIGEST, **overrides}
    return issue_token(KEY, ttl_seconds=ttl, now=now, **args)


def test_valid_token_verifies_and_carries_its_claims() -> None:
    parsed = verify_token(KEY, token(), claim_id="PH-5001", digest=DIGEST, now=1100.0)
    assert (parsed.claim_id, parsed.digest, parsed.expires_at) == ("PH-5001", DIGEST, 1900)
    assert len(parsed.jti) == 16


def test_each_token_has_its_own_id() -> None:
    first = verify_token(KEY, token(), claim_id="PH-5001", digest=DIGEST, now=1000.0)
    second = verify_token(KEY, token(), claim_id="PH-5001", digest=DIGEST, now=1000.0)
    assert first.jti != second.jti


def test_expired_token_is_rejected() -> None:
    with pytest.raises(TokenExpiredError):
        verify_token(KEY, token(), claim_id="PH-5001", digest=DIGEST, now=1900.0)


def test_token_is_valid_until_the_last_second() -> None:
    verify_token(KEY, token(), claim_id="PH-5001", digest=DIGEST, now=1899.0)


def test_tampered_payload_is_rejected() -> None:
    body, signature = token().split(".")
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")
    with pytest.raises(TokenInvalidError, match="signature"):
        verify_token(KEY, f"{forged}.{signature}", claim_id="PH-5001", digest=DIGEST, now=1100.0)


def test_tampered_signature_is_rejected() -> None:
    body, signature = token().split(".")
    other = "A" if signature[0] != "A" else "B"
    with pytest.raises(TokenInvalidError, match="signature"):
        verify_token(KEY, f"{body}.{other}{signature[1:]}", claim_id="PH-5001", digest=DIGEST)


def test_token_signed_with_another_key_is_rejected() -> None:
    with pytest.raises(TokenInvalidError, match="signature"):
        verify_token("z" * 32, token(), claim_id="PH-5001", digest=DIGEST, now=1100.0)


@pytest.mark.parametrize("bad", ["", "abc", "a.", ".b", "no-dot"])
def test_malformed_tokens_are_rejected(bad: str) -> None:
    with pytest.raises(TokenInvalidError, match="malformed|signature"):
        verify_token(KEY, bad, claim_id="PH-5001", digest=DIGEST)


def test_token_for_another_claim_is_rejected() -> None:
    with pytest.raises(TokenInvalidError, match="different claim"):
        verify_token(KEY, token(), claim_id="PH-5002", digest=DIGEST, now=1100.0)


def test_token_is_bound_to_the_exact_draft() -> None:
    changed = draft_digest({**DRAFT, "amount_claimed": "99999.00"})
    with pytest.raises(TokenInvalidError, match="draft changed"):
        verify_token(KEY, token(), claim_id="PH-5001", digest=changed, now=1100.0)


def test_digest_ignores_extra_fields_and_key_order() -> None:
    reordered = dict(reversed(list(DRAFT.items())))
    assert draft_digest(reordered) == DIGEST
    assert draft_digest({**DRAFT, "status": "draft", "created_at": "x"}) == DIGEST


def test_digest_changes_with_every_bound_field() -> None:
    for name, value in [("description", "x"), ("country", "sg"), ("incident_date", "2026-10-02")]:
        assert draft_digest({**DRAFT, name: value}) != DIGEST


def test_short_key_is_refused() -> None:
    with pytest.raises(ValueError, match="at least"):
        issue_token("short", claim_id="PH-1", digest="d", ttl_seconds=60)
    with pytest.raises(ValueError, match="at least"):
        verify_token(b"short", "a.b", claim_id="PH-1", digest="d")


def test_ttl_must_be_positive() -> None:
    with pytest.raises(ValueError, match="ttl"):
        issue_token(KEY, claim_id="PH-1", digest="d", ttl_seconds=0)


def test_bytes_and_str_keys_are_equivalent() -> None:
    signed = issue_token(KEY.encode(), claim_id="PH-5001", digest=DIGEST, ttl_seconds=60, now=0)
    verify_token(KEY, signed, claim_id="PH-5001", digest=DIGEST, now=1)


def test_peek_reads_a_signed_token_even_when_expired() -> None:
    parsed = peek_token(KEY, token())
    assert (parsed.claim_id, parsed.digest, parsed.expires_at) == ("PH-5001", DIGEST, 1900)


def test_peek_still_checks_the_signature() -> None:
    with pytest.raises(TokenInvalidError, match="signature"):
        peek_token("z" * 32, token())
    with pytest.raises(TokenInvalidError, match="malformed"):
        peek_token(KEY, "garbage")
