import os
from collections.abc import Mapping
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider

CONNECTION_STRING_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"
ENV_NAME = "APP_ENV"
ALLOWED_ENVS = ("dev", "staging", "prod")


def app_env(env: Mapping[str, str] | None = None) -> str:
    value = (os.environ if env is None else env).get(ENV_NAME, "unknown").strip().lower()
    return value if value in ALLOWED_ENVS else "unknown"


def configure(
    service_name: str,
    *,
    env: Mapping[str, str] | None = None,
    processors: tuple[SpanProcessor, ...] = (),
) -> TracerProvider | None:
    values = os.environ if env is None else env
    connection_string = values.get(CONNECTION_STRING_ENV, "")
    if not connection_string and not processors:
        return None
    if connection_string and not processors:
        from azure.identity import DefaultAzureCredential
        from azure.monitor.opentelemetry import configure_azure_monitor

        kwargs: dict[str, Any] = {
            "connection_string": connection_string,
            "credential": DefaultAzureCredential(),
            "resource": Resource.create({"service.name": service_name}),
            "logging_formatter": None,
        }
        configure_azure_monitor(**kwargs)
        provider = trace.get_tracer_provider()
        return provider if isinstance(provider, TracerProvider) else None
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    for processor in processors:
        provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return provider
