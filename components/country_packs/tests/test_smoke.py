import country_packs


def test_package_imports() -> None:
    assert "load_country_packs" in country_packs.__all__
