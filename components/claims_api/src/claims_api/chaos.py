import asyncio
import math
import random
from collections.abc import Awaitable, Callable

_Z_95 = 1.6448536269514722


class Chaos:
    def __init__(
        self,
        p50_ms: float,
        p95_ms: float,
        failure_rate: float,
        rng: random.Random | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._rng = rng or random.Random()
        self._sleep = sleep
        self._failure_rate = failure_rate
        self._mu = math.log(p50_ms / 1000) if p50_ms > 0 else None
        spread = p95_ms / p50_ms if p50_ms > 0 else 1.0
        self._sigma = math.log(max(spread, 1.0)) / _Z_95

    def delay_seconds(self) -> float:
        if self._mu is None:
            return 0.0
        return math.exp(self._rng.gauss(self._mu, self._sigma))

    def should_fail(self) -> bool:
        return self._rng.random() < self._failure_rate

    async def apply(self) -> bool:
        await self._sleep(self.delay_seconds())
        return self.should_fail()
