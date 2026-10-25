from collections.abc import Mapping
from pathlib import Path

from agent_app.config import ConfigError
from router import RoutingConfig, RoutingConfigError, parse_routing_config


def default_routing_path() -> Path:
    return Path(__file__).resolve().parents[3] / "router" / "routing.yaml"


def load_routing(path: str, known_deployments: Mapping[str, object]) -> RoutingConfig:
    source = Path(path) if path else default_routing_path()
    try:
        cfg = parse_routing_config(source.read_text(encoding="utf-8"))
    except (OSError, RoutingConfigError) as exc:
        raise ConfigError(f"routing config {source}: {exc}") from exc
    unknown = sorted(
        {name for names in cfg.deployments.values() for name in names} - set(known_deployments)
    )
    if unknown:
        raise ConfigError(
            f"routing config uses deployment(s) not in models.yaml: {', '.join(unknown)}"
        )
    return cfg
