from decimal import Decimal
from pathlib import Path

import pytest

from country_packs import (
    PackValidationError,
    load_all,
    load_country_pack,
    load_country_packs,
    load_model_catalog,
    prices_from_catalog,
)
from shared import cost_usd

FIXTURES = Path(__file__).parent / "fixtures" / "countries"
VALID = (FIXTURES / "zz.yaml").read_text(encoding="utf-8")


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_real_packs_load_for_all_five_markets() -> None:
    packs, catalog = load_all()
    assert sorted(packs) == ["id", "jp", "ph", "sg", "th"]
    assert packs["jp"].languages == ["ja", "en"]
    assert packs["jp"].azure_region == "japaneast"
    assert packs["ph"].monthly_budget_usd == Decimal(10)
    assert {d.tier for d in catalog.deployments.values()} >= {"small", "large"}


def test_search_filter_and_file_name_agree_for_real_packs() -> None:
    for code, pack in load_country_packs().items():
        assert pack.search_filter == f"country eq '{code}'"


def test_new_market_loads_with_config_only() -> None:
    packs = load_country_packs(FIXTURES)
    assert list(packs) == ["zz"]
    assert packs["zz"].name == "Fixtureland"


def test_new_market_next_to_real_ones_needs_no_code_change(tmp_path: Path) -> None:
    for real in (Path(__file__).parents[1] / "countries").glob("*.yaml"):
        write(tmp_path, real.name, real.read_text(encoding="utf-8"))
    write(tmp_path, "zz.yaml", VALID)
    assert sorted(load_country_packs(tmp_path)) == ["id", "jp", "ph", "sg", "th", "zz"]


def test_prices_feed_cost_calculation() -> None:
    prices = prices_from_catalog(load_model_catalog())
    assert cost_usd("small-a", 1_000_000, 0, 0, prices) > 0
    assert cost_usd("embedding", 0, 0, 1_000_000, prices) == 0


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("monthly_budget_usd: 5", "monthly_budget_usd: 0", "monthly_budget_usd"),
        ("retention_days: 7", "retention_days: -1", "retention_days"),
        ("deployment_type: regional", "deployment_type: planet", "deployment_type"),
        ("allowed_model_tiers: [small]", "allowed_model_tiers: [huge]", "allowed_model_tiers"),
        ("languages: [en]", "languages: [English]", "language codes"),
        ("languages: [en]", "languages: []", "languages"),
        ("code: zz", "code: zzz", "code"),
        (
            "search_filter: \"country eq 'zz'\"",
            "search_filter: \"country eq 'ph'\"",
            "search_filter",
        ),
        ("log_prompts: false\n", "log_prompts: false\nsurprise: 1\n", "surprise"),
        ("log_prompts: false\n", "", "log_prompts"),
    ],
)
def test_bad_pack_fails_with_readable_error(
    tmp_path: Path, old: str, new: str, expected: str
) -> None:
    path = write(tmp_path, "zz.yaml", VALID.replace(old, new))
    with pytest.raises(PackValidationError) as info:
        load_country_pack(path)
    message = str(info.value)
    assert str(path) in message
    assert expected in message


def test_code_must_match_file_name(tmp_path: Path) -> None:
    path = write(tmp_path, "yy.yaml", VALID)
    with pytest.raises(PackValidationError, match="does not match the file name 'yy'"):
        load_country_pack(path)


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    path = write(tmp_path, "zz.yaml", "code: [unclosed")
    with pytest.raises(PackValidationError, match="invalid YAML"):
        load_country_pack(path)


def test_top_level_must_be_a_mapping(tmp_path: Path) -> None:
    path = write(tmp_path, "zz.yaml", "- just\n- a list\n")
    with pytest.raises(PackValidationError, match="mapping"):
        load_country_pack(path)


def test_one_bad_pack_stops_loading_the_directory(tmp_path: Path) -> None:
    write(tmp_path, "zz.yaml", VALID)
    write(tmp_path, "yy.yaml", "code: yy\n")
    with pytest.raises(PackValidationError, match="yy.yaml"):
        load_country_packs(tmp_path)


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PackValidationError, match="no country pack files"):
        load_country_packs(tmp_path)


def test_catalog_needs_both_tiers(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "models.yaml",
        "deployments:\n  only:\n    tier: small\n    model: m\n    version: v1\n"
        "    prices: {input_per_1m: 1, cached_input_per_1m: 1, output_per_1m: 1}\n",
    )
    with pytest.raises(PackValidationError, match="no deployment for tier"):
        load_model_catalog(path)


def test_catalog_rejects_negative_price(tmp_path: Path) -> None:
    text = (Path(__file__).parents[1] / "models.yaml").read_text(encoding="utf-8")
    path = write(
        tmp_path, "models.yaml", text.replace("output_per_1m: 1.60", "output_per_1m: -1", 1)
    )
    with pytest.raises(PackValidationError, match="output_per_1m"):
        load_model_catalog(path)


def test_missing_catalog_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PackValidationError, match="cannot read file"):
        load_model_catalog(tmp_path / "nope.yaml")


def test_root_can_be_overridden_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "countries").mkdir()
    write(tmp_path / "countries", "zz.yaml", VALID)
    write(tmp_path, "models.yaml", (Path(__file__).parents[1] / "models.yaml").read_text("utf-8"))
    monkeypatch.setenv("COUNTRY_PACKS_DIR", str(tmp_path))
    packs, _ = load_all()
    assert list(packs) == ["zz"]
