import importlib.util
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "package_budget",
    Path(__file__).resolve().parent.parent / "tools" / "package_budget_function.py",
)
assert spec and spec.loader
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


def test_the_zip_holds_everything_the_function_imports_and_reads(tmp_path: Path) -> None:
    target = tmp_path / "f.zip"
    count = pkg.build(target)
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
    assert count == len(names)
    for needed in (
        "function_app.py",
        "host.json",
        "requirements.txt",
        "budget_controller/run.py",
        "telemetry/spans.py",
        "shared/pricing.py",
        "country_packs/loader.py",
        "country_packs/models.yaml",
        "country_packs/countries/ph.yaml",
        "kql/spend_by_country.kql",
    ):
        assert needed in names, needed
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    assert not any(n.startswith(("tests/", "web_ui", "agent_app", "rag/")) for n in names)


def test_every_country_pack_is_included_so_budgets_cover_all_markets(tmp_path: Path) -> None:
    packs = {p.name for p in (pkg.COMPONENTS / "country_packs" / "countries").glob("*.yaml")}
    names = set(pkg.entries())
    assert {f"country_packs/countries/{p}" for p in packs} <= names
