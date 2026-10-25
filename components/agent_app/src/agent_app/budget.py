import json
import logging
import time
from collections.abc import Callable
from typing import Any

from router import BudgetState

log = logging.getLogger(__name__)
VALID: tuple[BudgetState, ...] = ("ok", "warn", "exceeded")
STATE_BLOB = "state.json"
CAUTIOUS: BudgetState = "warn"


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
        self._loaded = False
        self._loaded_at: float | None = None

    def __call__(self, country: str) -> BudgetState:
        now = self._clock()
        if self._loaded_at is None or now - self._loaded_at >= self._ttl:
            self._refresh(now)
        if not self._loaded:
            return CAUTIOUS
        return self._states.get(country, "ok")

    def _refresh(self, now: float) -> None:
        try:
            data = json.loads(self._fetch())["states"]
            if any(value not in VALID for value in data.values()):
                log.error("budget state has an unrecognised value; treating it as warn")
            self._states = {
                str(country): (value if value in VALID else CAUTIOUS)
                for country, value in data.items()
            }
            self._loaded = True
        except Exception:  # noqa: BLE001
            log.error("budget state unreadable; using the last known state or warn", exc_info=True)
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

    def fetch() -> bytes:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return bytes(blob.download_blob().readall())
        except ResourceNotFoundError:
            return b'{"version": 1, "states": {}}'

    return fetch
