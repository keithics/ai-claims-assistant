import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECT_HOST = re.compile(
    r"[\w-]+\.(openai\.azure\.com|cognitiveservices\.azure\.com|services\.ai\.azure\.com)", re.I
)
SCANNED = [
    "components/agent_app/src",
    "components/agent_app/Dockerfile",
    "components/rag/src",
    "components/web_ui/src",
    "components/web_ui/public",
    "components/web_ui/Dockerfile",
    "components/web_ui/docker-entrypoint.d",
    "components/claims_api/src",
    "components/country_packs/countries",
    "components/country_packs/models.yaml",
    "infra/modules/container_apps",
    "infra/envs/dev/terraform.tfvars.example",
    "infra/envs/staging/terraform.tfvars.example",
    "tools",
    "Makefile",
]
SKIP_DIRS = {"node_modules", "__pycache__", ".terraform", "dist", ".venv", "tests"}
LEGACY_FLAGS = ("ALLOW_DIRECT", "allow_direct", "AGENT_MODEL_ENDPOINT", "RAG_EMBEDDING_ENDPOINT")


def files() -> list[Path]:
    found: list[Path] = []
    for entry in SCANNED:
        path = ROOT / entry
        candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
        for candidate in candidates:
            if candidate.is_file() and not SKIP_DIRS & set(candidate.parts):
                found.append(candidate)
    return found


def read(path: Path) -> str:
    try:
        return path.read_text()
    except UnicodeDecodeError:
        return ""


def test_the_scan_actually_covers_files() -> None:
    names = {p.name for p in files()}
    assert {"config.py", "llm.py", "Makefile", "main.tf", "run_local.py"} <= names


def test_no_app_config_contains_a_direct_model_endpoint_hostname() -> None:
    offenders = {
        str(p.relative_to(ROOT)): DIRECT_HOST.search(read(p)).group(0)  # type: ignore[union-attr]
        for p in files()
        if DIRECT_HOST.search(read(p))
    }
    assert offenders == {}


def test_the_direct_endpoint_dev_flags_are_gone() -> None:
    offenders = {
        str(p.relative_to(ROOT)): flag for p in files() for flag in LEGACY_FLAGS if flag in read(p)
    }
    assert offenders == {}
