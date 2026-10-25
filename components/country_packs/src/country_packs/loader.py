import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from country_packs.schema import CountryPack, ModelCatalog
from shared import ModelPrice


class PackValidationError(ValueError):
    pass


def default_root() -> Path:
    override = os.environ.get("COUNTRY_PACKS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2]


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PackValidationError(f"{path}: invalid YAML: {exc}") from exc
    except OSError as exc:
        raise PackValidationError(f"{path}: cannot read file: {exc}") from exc


def _describe(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        where = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"  {where}: {error['msg']}")
    return "\n".join(lines)


def load_country_pack(path: Path) -> CountryPack:
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise PackValidationError(f"{path}: expected a mapping at the top level")
    try:
        pack = CountryPack.model_validate(data)
    except ValidationError as exc:
        raise PackValidationError(f"{path}: invalid country pack\n{_describe(exc)}") from exc
    if pack.code != path.stem:
        raise PackValidationError(
            f"{path}: code {pack.code!r} does not match the file name {path.stem!r}"
        )
    return pack


def load_country_packs(countries_dir: Path | None = None) -> dict[str, CountryPack]:
    directory = countries_dir or default_root() / "countries"
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise PackValidationError(f"{directory}: no country pack files (*.yaml) found")
    return {pack.code: pack for pack in (load_country_pack(f) for f in files)}


def load_model_catalog(path: Path | None = None) -> ModelCatalog:
    file = path or default_root() / "models.yaml"
    data = _read_yaml(file)
    if not isinstance(data, dict):
        raise PackValidationError(f"{file}: expected a mapping at the top level")
    try:
        return ModelCatalog.model_validate(data)
    except ValidationError as exc:
        raise PackValidationError(f"{file}: invalid model catalog\n{_describe(exc)}") from exc


def prices_from_catalog(catalog: ModelCatalog) -> dict[str, ModelPrice]:
    return {
        name: ModelPrice(
            input_per_1m=entry.prices.input_per_1m,
            cached_input_per_1m=entry.prices.cached_input_per_1m,
            output_per_1m=entry.prices.output_per_1m,
        )
        for name, entry in catalog.deployments.items()
    }


def load_all(root: Path | None = None) -> tuple[dict[str, CountryPack], ModelCatalog]:
    base = root or default_root()
    return load_country_packs(base / "countries"), load_model_catalog(base / "models.yaml")
