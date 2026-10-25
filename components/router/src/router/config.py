import yaml
from pydantic import ValidationError

from router.models import RoutingConfig


class RoutingConfigError(ValueError):
    pass


def parse_routing_config(text: str) -> RoutingConfig:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RoutingConfigError(f"routing config is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RoutingConfigError("routing config must be a YAML mapping")
    try:
        return RoutingConfig.model_validate(data)
    except ValidationError as exc:
        raise RoutingConfigError(f"routing config is invalid: {exc}") from exc
