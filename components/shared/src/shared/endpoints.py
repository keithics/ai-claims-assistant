from collections.abc import Mapping
from urllib.parse import urlparse

DIRECT_MODEL_HOST_SUFFIXES = (
    ".openai.azure.com",
    ".cognitiveservices.azure.com",
    ".services.ai.azure.com",
)
GATEWAY_KEY_PREFIX = "GATEWAY_KEY_"


class EndpointError(ValueError):
    pass


def check_gateway_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise EndpointError(f"gateway URL is not a valid URL: {url!r}")
    if host.endswith(DIRECT_MODEL_HOST_SUFFIXES):
        raise EndpointError(
            f"{host} is a direct model endpoint. Apps call models through the gateway only."
        )


def gateway_keys_from_env(env: Mapping[str, str]) -> dict[str, str]:
    return {
        name[len(GATEWAY_KEY_PREFIX) :].lower(): value
        for name, value in env.items()
        if name.startswith(GATEWAY_KEY_PREFIX) and value
    }
