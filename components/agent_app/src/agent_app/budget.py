import json
import logging
import time
from collections.abc import Callable
from typing import Any

from router import BudgetState

log = logging.getLogger(__name__)
VALID: tuple[BudgetState, ...] = ("ok", "warn", "exceeded")
STATE_BLOB = "state.json"


class BudgetStateReader:
    def __init__(
        self,
        fetch: Callable[[], bytes | str],
        *,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._clock = clock
        self._states: dict[str, BudgetState] = {}
        self._loaded_at: float | None = None

    def __call__(self, country: str) -> BudgetState:
        now = self._clock()
        if self._loaded_at is None or now - self._loaded_at >= self._ttl:
            self._refresh(now)
        return self._states.get(country, "ok")

    def _refresh(self, now: float) -> None:
        try:
            data = json.loads(self._fetch())["states"]
            states = {str(k): v for k, v in data.items() if v in VALID}
        except Exception:  # noqa: BLE001
            log.warning("budget state unavailable; keeping the last known state", exc_info=True)
            states = self._states
        self._states = states
        self._loaded_at = now


def blob_fetcher(account_url: str, container: str, credential: Any = None) -> Callable[[], bytes]:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobClient

    blob = BlobClient(
        account_url,
        container_name=container,
        blob_name=STATE_BLOB,
        credential=credential or DefaultAzureCredential(),
    )
    return lambda: bytes(blob.download_blob().readall())
