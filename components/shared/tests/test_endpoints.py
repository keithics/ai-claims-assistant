import pytest

from shared import EndpointError, check_gateway_url, gateway_keys_from_env


@pytest.mark.parametrize(
    "url",
    [
        "https://apim-claims-assistant-dev.azure-api.net",
        "https://gateway.example.com/models",
        "http://localhost:8080",
    ],
)
def test_gateway_urls_are_accepted(url: str) -> None:
    check_gateway_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://ais-dev.openai.azure.com/",
        "https://AIS-DEV.OPENAI.AZURE.COM/openai",
        "https://ais-dev.cognitiveservices.azure.com",
        "https://proj.services.ai.azure.com/api",
    ],
)
def test_direct_model_endpoints_are_always_rejected(url: str) -> None:
    with pytest.raises(EndpointError, match="direct model endpoint"):
        check_gateway_url(url)


@pytest.mark.parametrize("url", ["", "not a url", "https://"])
def test_invalid_urls_are_rejected(url: str) -> None:
    with pytest.raises(EndpointError, match="not a valid URL"):
        check_gateway_url(url)


def test_keys_are_read_per_country_and_empty_values_are_ignored() -> None:
    env = {
        "GATEWAY_KEY_PH": "k1",
        "GATEWAY_KEY_TH": "k2",
        "GATEWAY_KEY_JP": "",
        "GATEWAY_CLAIMS_KEY": "other",
        "PATH": "/bin",
    }
    assert gateway_keys_from_env(env) == {"ph": "k1", "th": "k2"}
