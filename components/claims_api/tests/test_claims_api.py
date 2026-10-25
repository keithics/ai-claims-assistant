import random
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claims_api import Chaos, ConfigError, Settings, create_app, digest_of
from claims_api.models import Claim
from shared import draft_digest, issue_token

KEY = "test-signing-key-0123456789"
SEED = Path(__file__).parents[1] / "seed"
DRAFT = {
    "country": "ph",
    "claim_type": "motor",
    "incident_date": "2026-10-20",
    "description": "Rear-ended at a junction",
    "amount_claimed": "12000.50",
    "policy_number": "POL-PH-1207280",
}


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "signing_key": KEY,
        "seed_dir": SEED,
        "latency_p50_ms": 0,
        "latency_p95_ms": 0,
        "failure_rate": 0.0,
        "random_seed": 1,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as c:
        yield c


def mint(claim: dict[str, object], now: float = 1_000.0, ttl: int = 900) -> str:
    parsed = Claim.model_validate(claim)
    return issue_token(
        KEY, claim_id=parsed.claim_id, digest=digest_of(parsed), ttl_seconds=ttl, now=now
    )


def draft(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/claims", json={**DRAFT, **overrides})
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_healthz_is_never_flaky() -> None:
    with TestClient(create_app(make_settings(failure_rate=1.0))) as c:
        assert c.get("/healthz").json() == {"status": "ok"}


def test_every_market_is_seeded_with_ids_like_ph_1042(client: TestClient) -> None:
    for code in ("ph", "sg", "id", "th", "jp"):
        body = client.get(f"/claims/{code.upper()}-1042").json()
        assert body["claim_id"] == f"{code.upper()}-1042"
        assert body["country"] == code and body["status"] != "draft"


def test_get_claim_returns_the_claim_and_accepts_lowercase(client: TestClient) -> None:
    body = client.get("/claims/ph-1042").json()
    assert body["claim_id"] == "PH-1042"
    assert set(body) >= {"claim_type", "incident_date", "amount_claimed", "currency", "status"}


def test_unknown_claim_is_404_with_a_code(client: TestClient) -> None:
    response = client.get("/claims/PH-9999")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


@pytest.mark.parametrize("claim_id", ["nonsense", "PH1042", "PHX-1042", "PH-12"])
def test_malformed_claim_id_is_422(client: TestClient, claim_id: str) -> None:
    assert client.get(f"/claims/{claim_id}").status_code == 422


def test_create_draft_assigns_ids_per_country_and_currency(client: TestClient) -> None:
    first, second = draft(client), draft(client)
    jp = draft(client, country="jp")
    assert (first["claim_id"], second["claim_id"], jp["claim_id"]) == (
        "PH-5001",
        "PH-5002",
        "JP-5001",
    )
    assert first["status"] == "draft" and first["currency"] == "PHP" and jp["currency"] == "JPY"
    assert client.get("/claims/PH-5001").json()["status"] == "draft"


@pytest.mark.parametrize(
    "overrides",
    [
        {"country": "PH"},
        {"claim_type": "boat"},
        {"incident_date": "yesterday"},
        {"description": ""},
        {"amount_claimed": "-5"},
        {"policy_number": "123"},
        {"surprise": True},
    ],
)
def test_bad_draft_requests_are_422(client: TestClient, overrides: dict[str, object]) -> None:
    assert client.post("/claims", json={**DRAFT, **overrides}).status_code == 422


def test_filing_needs_an_approval_token(client: TestClient) -> None:
    claim = draft(client)
    response = client.post(f"/claims/{claim['claim_id']}/file")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "approval_required"
    assert client.get(f"/claims/{claim['claim_id']}").json()["status"] == "draft"


def test_filing_with_a_valid_token_submits_the_claim() -> None:
    clock = [1_100.0]
    with TestClient(create_app(make_settings(), clock=lambda: clock[0])) as c:
        claim = draft(c)
        response = c.post(
            f"/claims/{claim['claim_id']}/file", headers={"X-Approval-Token": mint(claim)}
        )
        assert response.status_code == 200, response.text
        filed = response.json()
        assert filed["status"] == "submitted" and filed["filed_at"]
        assert c.get(f"/claims/{claim['claim_id']}").json()["status"] == "submitted"


def test_token_cannot_be_used_twice() -> None:
    with TestClient(create_app(make_settings(), clock=lambda: 1_100.0)) as c:
        claim = draft(c)
        token = mint(claim)
        assert (
            c.post(
                f"/claims/{claim['claim_id']}/file", headers={"X-Approval-Token": token}
            ).status_code
            == 200
        )
        again = c.post(f"/claims/{claim['claim_id']}/file", headers={"X-Approval-Token": token})
        assert again.status_code == 409
        assert again.json()["detail"]["code"] == "not_a_draft"


def test_expired_token_is_rejected() -> None:
    with TestClient(create_app(make_settings(), clock=lambda: 5_000.0)) as c:
        claim = draft(c)
        response = c.post(
            f"/claims/{claim['claim_id']}/file",
            headers={"X-Approval-Token": mint(claim, now=1_000.0)},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "token_expired"
        assert c.get(f"/claims/{claim['claim_id']}").json()["status"] == "draft"


def test_token_for_another_claim_is_rejected() -> None:
    with TestClient(create_app(make_settings(), clock=lambda: 1_100.0)) as c:
        first, second = draft(c), draft(c)
        response = c.post(
            f"/claims/{second['claim_id']}/file", headers={"X-Approval-Token": mint(first)}
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "token_invalid"


def test_tampered_or_foreign_tokens_are_rejected() -> None:
    with TestClient(create_app(make_settings(), clock=lambda: 1_100.0)) as c:
        claim = draft(c)
        forged = issue_token(
            "another-key-0123456789abcdef",
            claim_id=str(claim["claim_id"]),
            digest=draft_digest(claim),
            ttl_seconds=900,
            now=1_000.0,
        )
        for token in (forged, mint(claim)[:-3] + "xyz", "garbage"):
            response = c.post(
                f"/claims/{claim['claim_id']}/file", headers={"X-Approval-Token": token}
            )
            assert response.status_code == 401
        assert c.get(f"/claims/{claim['claim_id']}").json()["status"] == "draft"


def test_token_is_bound_to_the_exact_draft() -> None:
    with TestClient(create_app(make_settings(), clock=lambda: 1_100.0)) as c:
        claim = draft(c)
        other = {**claim, "amount_claimed": "999999.00"}
        response = c.post(
            f"/claims/{claim['claim_id']}/file", headers={"X-Approval-Token": mint(other)}
        )
        assert response.status_code == 401
        assert "draft changed" in response.json()["detail"]["message"]


def test_seeded_claims_cannot_be_filed(client: TestClient) -> None:
    claim = client.get("/claims/PH-1042").json()
    response = client.post("/claims/PH-1042/file", headers={"X-Approval-Token": mint(claim)})
    assert response.status_code == 409


def test_filing_unknown_claim_is_404(client: TestClient) -> None:
    assert client.post("/claims/PH-9999/file", headers={"X-Approval-Token": "x"}).status_code == 404


def test_failure_rate_one_always_gives_503() -> None:
    with TestClient(create_app(make_settings(failure_rate=1.0))) as c:
        for _ in range(5):
            response = c.get("/claims/PH-1042")
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "unavailable"


def test_failure_rate_zero_never_fails(client: TestClient) -> None:
    assert all(client.get("/claims/PH-1042").status_code == 200 for _ in range(100))


def test_failure_injection_hits_the_configured_rate() -> None:
    chaos = Chaos(0, 0, 0.05, rng=random.Random(42))
    failures = sum(chaos.should_fail() for _ in range(20_000))
    assert 0.04 <= failures / 20_000 <= 0.06


def test_failures_through_the_api_are_roughly_five_percent() -> None:
    settings = make_settings(failure_rate=0.05, random_seed=7)
    with TestClient(create_app(settings)) as c:
        codes = [c.get("/claims/PH-1042").status_code for _ in range(1_000)]
    assert set(codes) <= {200, 503}
    assert 0.03 <= codes.count(503) / 1_000 <= 0.07


def test_latency_has_the_configured_median_and_p95() -> None:
    chaos = Chaos(800, 3000, 0.0, rng=random.Random(3))
    samples = sorted(chaos.delay_seconds() for _ in range(20_000))
    p50, p95 = samples[10_000], samples[int(20_000 * 0.95)]
    assert 0.72 <= p50 <= 0.88
    assert 2.6 <= p95 <= 3.4


def test_zero_latency_never_sleeps() -> None:
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    chaos = Chaos(0, 0, 0.0, sleep=record)
    import asyncio

    asyncio.run(chaos.apply())
    assert slept == [0.0]


def test_delay_is_applied_before_responding() -> None:
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    chaos = Chaos(800, 3000, 0.0, rng=random.Random(1), sleep=record)
    with TestClient(create_app(make_settings(), chaos=chaos)) as c:
        c.get("/claims/PH-1042")
    assert len(slept) == 1 and slept[0] > 0


def test_settings_from_env() -> None:
    settings = Settings.from_env({"APPROVAL_SIGNING_KEY": KEY})
    assert (settings.latency_p50_ms, settings.latency_p95_ms, settings.failure_rate) == (
        800,
        3000,
        0.05,
    )
    tuned = Settings.from_env(
        {"APPROVAL_SIGNING_KEY": KEY, "CLAIMS_API_FAILURE_RATE": "0.5", "CLAIMS_API_SEED": "9"}
    )
    assert tuned.failure_rate == 0.5 and tuned.random_seed == 9


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"APPROVAL_SIGNING_KEY": "short"},
        {"APPROVAL_SIGNING_KEY": KEY, "CLAIMS_API_FAILURE_RATE": "2"},
        {"APPROVAL_SIGNING_KEY": KEY, "CLAIMS_API_FAILURE_RATE": "lots"},
        {
            "APPROVAL_SIGNING_KEY": KEY,
            "CLAIMS_API_LATENCY_P50_MS": "900",
            "CLAIMS_API_LATENCY_P95_MS": "100",
        },
    ],
)
def test_bad_settings_fail_fast(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_missing_seed_dir_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_app(make_settings(seed_dir=tmp_path))
