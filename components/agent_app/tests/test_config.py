import pytest

from agent_app import ConfigError, Settings

ENV = {
    "AGENT_GATEWAY_URL": "https://gw.azure-api.net",
    "GATEWAY_KEY_PH": "key-ph",
    "GATEWAY_KEY_TH": "key-th",
    "RAG_SEARCH_ENDPOINT": "https://s.search.windows.net",
    "APPROVAL_SIGNING_KEY": "test-approval-key-0123456789",
}


def test_defaults() -> None:
    settings = Settings.from_env(ENV)
    assert settings.chat_deployment == "small-a" and settings.top_k == 5
    assert settings.index_name == "policies" and settings.max_output_tokens == 600
    assert (
        settings.approval_ttl_seconds == 900
        and settings.max_steps == 6
        and settings.claims_api_url == "http://localhost:8001"
    )


def test_overrides() -> None:
    env = {**ENV, "AGENT_CHAT_DEPLOYMENT": "large", "AGENT_TOP_K": "3", "RAG_INDEX_NAME": "x"}
    settings = Settings.from_env(env)
    assert (settings.chat_deployment, settings.top_k, settings.index_name) == ("large", 3, "x")


def test_missing_variables_are_named() -> None:
    with pytest.raises(
        ConfigError, match="AGENT_GATEWAY_URL, RAG_SEARCH_ENDPOINT, APPROVAL_SIGNING_KEY"
    ):
        Settings.from_env({})


@pytest.mark.parametrize(
    "url",
    [
        "https://a.openai.azure.com/",
        "https://a.cognitiveservices.azure.com/",
        "https://a.services.ai.azure.com/api",
    ],
)
def test_direct_model_endpoints_are_always_refused(url: str) -> None:
    with pytest.raises(ConfigError, match="direct model endpoint"):
        Settings.from_env({**ENV, "AGENT_GATEWAY_URL": url})


def test_no_flag_can_allow_a_direct_endpoint() -> None:
    env = {
        **ENV,
        "AGENT_GATEWAY_URL": "https://a.openai.azure.com/",
        "AGENT_DEV_ALLOW_DIRECT_MODEL_ENDPOINT": "true",
    }
    with pytest.raises(ConfigError, match="direct model endpoint"):
        Settings.from_env(env)


def test_country_keys_and_claims_key_are_read() -> None:
    settings = Settings.from_env({**ENV, "GATEWAY_CLAIMS_KEY": "ck"})
    assert settings.gateway_keys == {"ph": "key-ph", "th": "key-th"}
    assert settings.claims_api_key == "ck"


def test_a_country_key_is_required() -> None:
    env = {k: v for k, v in ENV.items() if not k.startswith("GATEWAY_KEY_")}
    with pytest.raises(ConfigError, match="GATEWAY_KEY_"):
        Settings.from_env(env)


@pytest.mark.parametrize(
    "extra",
    [
        {"AGENT_TOP_K": "0"},
        {"AGENT_TOP_K": "many"},
        {"AGENT_MAX_OUTPUT_TOKENS": "-5"},
        {"AGENT_MAX_STEPS": "0"},
    ],
)
def test_bad_numbers_are_rejected(extra: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({**ENV, **extra})
