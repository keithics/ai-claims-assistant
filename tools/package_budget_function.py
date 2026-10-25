import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "components"
PACKAGES = {
    "budget_controller": COMPONENTS / "budget_controller" / "src" / "budget_controller",
    "telemetry": COMPONENTS / "telemetry" / "src" / "telemetry",
    "shared": COMPONENTS / "shared" / "src" / "shared",
    "country_packs": COMPONENTS / "country_packs" / "src" / "country_packs",
}
FILES = {
    "function_app.py": COMPONENTS / "budget_controller" / "function_app.py",
    "host.json": COMPONENTS / "budget_controller" / "host.json",
    "requirements.txt": COMPONENTS / "budget_controller" / "requirements.txt",
    "kql/spend_by_country.kql": COMPONENTS / "telemetry" / "kql" / "spend_by_country.kql",
    "country_packs/models.yaml": COMPONENTS / "country_packs" / "models.yaml",
}
SKIP = ("__pycache__", ".pyc")


def entries() -> dict[str, Path]:
    found: dict[str, Path] = dict(FILES)
    for name, source in PACKAGES.items():
        for path in sorted(source.rglob("*")):
            if path.is_file() and not any(part in str(path) for part in SKIP):
                found[f"{name}/{path.relative_to(source)}"] = path
    for path in sorted((COMPONENTS / "country_packs" / "countries").glob("*.yaml")):
        found[f"country_packs/countries/{path.name}"] = path
    return found


def build(target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in entries().items():
            archive.write(path, name)
    return len(entries())


def main() -> int:
    parser = argparse.ArgumentParser(description="Zip the budget controller for Flex Consumption.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "budget_controller.zip")
    args = parser.parse_args()
    missing = [str(p) for p in [*FILES.values(), *PACKAGES.values()] if not p.exists()]
    if missing:
        print(f"package-budget: missing {missing}", file=sys.stderr)
        return 2
    if args.out.exists():
        args.out.unlink()
    count = build(args.out)
    print(f"package-budget: wrote {args.out} ({count} files, {args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
