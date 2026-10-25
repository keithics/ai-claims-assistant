import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CURRENCIES = {"ph": "PHP", "sg": "SGD", "id": "IDR", "th": "THB", "jp": "JPY"}


class ConfigError(ValueError):
    pass


def default_seed_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "seed"


@dataclass(frozen=True)
class Settings:
    signing_key: str
    seed_dir: Path
    latency_p50_ms: float = 800.0
    latency_p95_ms: float = 3000.0
    failure_rate: float = 0.05
    random_seed: int | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        key = values.get("APPROVAL_SIGNING_KEY", "")
        if len(key) < 16:
            raise ConfigError("APPROVAL_SIGNING_KEY is missing or shorter than 16 characters")
        try:
            settings = cls(
                signing_key=key,
                seed_dir=Path(values.get("CLAIMS_API_SEED_DIR", str(default_seed_dir()))),
                latency_p50_ms=float(values.get("CLAIMS_API_LATENCY_P50_MS", "800")),
                latency_p95_ms=float(values.get("CLAIMS_API_LATENCY_P95_MS", "3000")),
                failure_rate=float(values.get("CLAIMS_API_FAILURE_RATE", "0.05")),
                random_seed=(
                    int(values["CLAIMS_API_SEED"]) if values.get("CLAIMS_API_SEED") else None
                ),
            )
        except ValueError as exc:
            raise ConfigError(f"invalid number in claims API settings: {exc}") from exc
        if not 0 <= settings.failure_rate <= 1:
            raise ConfigError("CLAIMS_API_FAILURE_RATE must be between 0 and 1")
        if settings.latency_p50_ms < 0 or settings.latency_p95_ms < settings.latency_p50_ms:
            raise ConfigError("latency p95 must be at least p50, and both non-negative")
        return settings
