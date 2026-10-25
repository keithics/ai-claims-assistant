import os
from collections.abc import Mapping
from dataclasses import dataclass

from shared import EndpointError, check_gateway_url, gateway_keys_from_env


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    gateway_url: str
    gateway_keys: Mapping[str, str]
    search_endpoint: str
    chat_deployment: str = "small-a"
    embedding_deployment: str = "embedding"
    index_name: str = "policies"
    api_version: str = "2024-10-21"
    top_k: int = 5
    max_output_tokens: int = 600
    max_steps: int = 6
    claims_api_url: str = "http://localhost:8001"
    approval_signing_key: str = ""
    approval_ttl_seconds: int = 900
    claims_api_key: str = ""
    allow_tier_override: bool = False
    routing_path: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        required = ("AGENT_GATEWAY_URL", "RAG_SEARCH_ENDPOINT", "APPROVAL_SIGNING_KEY")
        missing = [name for name in required if not values.get(name)]
        if missing:
            raise ConfigError(f"missing environment variable(s): {', '.join(missing)}")
        keys = gateway_keys_from_env(values)
        if not keys:
            raise ConfigError("no GATEWAY_KEY_<COUNTRY> variables are set")
        try:
            check_gateway_url(values["AGENT_GATEWAY_URL"])
            top_k = int(values.get("AGENT_TOP_K", "5"))
            max_output_tokens = int(values.get("AGENT_MAX_OUTPUT_TOKENS", "600"))
            max_steps = int(values.get("AGENT_MAX_STEPS", "6"))
            approval_ttl = int(values.get("AGENT_APPROVAL_TTL_SECONDS", "900"))
        except (EndpointError, ValueError) as exc:
            raise ConfigError(str(exc)) from exc
        if len(values["APPROVAL_SIGNING_KEY"]) < 16:
            raise ConfigError("APPROVAL_SIGNING_KEY must be at least 16 characters")
        if min(top_k, max_output_tokens, max_steps, approval_ttl) <= 0:
            raise ConfigError(
                "AGENT_TOP_K, AGENT_MAX_OUTPUT_TOKENS, AGENT_MAX_STEPS and "
                "AGENT_APPROVAL_TTL_SECONDS must be positive"
            )
        return cls(
            gateway_url=values["AGENT_GATEWAY_URL"],
            gateway_keys=keys,
            search_endpoint=values["RAG_SEARCH_ENDPOINT"],
            chat_deployment=values.get("AGENT_CHAT_DEPLOYMENT", "small-a"),
            embedding_deployment=values.get("AGENT_EMBEDDING_DEPLOYMENT", "embedding"),
            index_name=values.get("RAG_INDEX_NAME", "policies"),
            api_version=values.get("AGENT_API_VERSION", "2024-10-21"),
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            max_steps=max_steps,
            claims_api_url=values.get("CLAIMS_API_URL", "http://localhost:8001"),
            approval_signing_key=values["APPROVAL_SIGNING_KEY"],
            approval_ttl_seconds=approval_ttl,
            claims_api_key=values.get("GATEWAY_CLAIMS_KEY", ""),
            allow_tier_override=values.get("AGENT_ALLOW_TIER_OVERRIDE", "").lower()
            in {"1", "true"},
            routing_path=values.get("ROUTING_CONFIG_PATH", ""),
        )
