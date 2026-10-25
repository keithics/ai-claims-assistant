import time
from collections.abc import Callable
from typing import Any, Literal, Protocol

import httpx

RETRYABLE = {503}


class ClaimsApiError(RuntimeError):
    def __init__(
        self, kind: Literal["not_found", "bad_request", "unavailable", "rejected"], message: str
    ):
        super().__init__(message)
        self.kind = kind


class ClaimsGateway(Protocol):
    def get_claim(self, claim_id: str) -> dict[str, Any]: ...

    def create_draft(self, draft: dict[str, Any]) -> dict[str, Any]: ...


class ClaimsFiler(Protocol):
    def file_claim(self, claim_id: str, token: str) -> dict[str, Any]: ...


class ClaimsClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        attempts: int = 3,
        backoff_seconds: float = 0.2,
        timeout_seconds: float = 6.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if client is None and base_url is None:
            raise ValueError("base_url or client is required")
        self._client = client or httpx.Client(
            base_url=base_url or "",
            timeout=timeout_seconds,
            headers={"api-key": api_key} if api_key else {},
        )
        self._attempts = attempts
        self._backoff = backoff_seconds
        self._sleep = sleep

    def _send(
        self, method: str, url: str, *, retry_transport: bool, **kwargs: Any
    ) -> dict[str, Any]:
        last = "claims system is unavailable"
        for attempt in range(self._attempts):
            if attempt:
                self._sleep(self._backoff * 2 ** (attempt - 1))
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last = f"claims system did not respond ({type(exc).__name__})"
                if retry_transport:
                    continue
                break
            if response.status_code in RETRYABLE:
                last = "claims system is temporarily unavailable"
                continue
            return self._interpret(response)
        raise ClaimsApiError("unavailable", last)

    @staticmethod
    def _interpret(response: httpx.Response) -> dict[str, Any]:
        if response.is_success:
            body: dict[str, Any] = response.json()
            return body
        try:
            detail = response.json().get("detail", {})
        except ValueError:
            detail = {}
        message = detail.get("message") if isinstance(detail, dict) else None
        message = message or f"claims system returned {response.status_code}"
        if response.status_code == 404:
            raise ClaimsApiError("not_found", message)
        if response.status_code in {400, 422}:
            raise ClaimsApiError("bad_request", message)
        if response.status_code in {401, 409}:
            raise ClaimsApiError("rejected", message)
        raise ClaimsApiError("unavailable", message)

    def get_claim(self, claim_id: str) -> dict[str, Any]:
        return self._send(
            "GET", f"/claims/{claim_id}", retry_transport=True, headers=_country_header(claim_id)
        )

    def create_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        return self._send(
            "POST",
            "/claims",
            retry_transport=False,
            json=draft,
            headers={"x-country": str(draft.get("country", "")).lower()},
        )

    def file_claim(self, claim_id: str, token: str) -> dict[str, Any]:
        return self._send(
            "POST",
            f"/claims/{claim_id}/file",
            retry_transport=False,
            headers={"X-Approval-Token": token, **_country_header(claim_id)},
        )


def _country_header(claim_id: str) -> dict[str, str]:
    return {"x-country": claim_id.split("-", 1)[0].lower()}


class RestrictedClaims:
    def __init__(self, client: ClaimsClient) -> None:
        self._get = client.get_claim
        self._draft = client.create_draft

    def get_claim(self, claim_id: str) -> dict[str, Any]:
        return self._get(claim_id)

    def create_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        return self._draft(draft)
