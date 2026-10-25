import json
import sys
from pathlib import Path

from agent_app.main import create_app


def default_path() -> Path:
    return Path(__file__).resolve().parents[2] / "openapi.json"


def render() -> str:
    schema = create_app(cors_origins=["http://localhost:5173"]).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else default_path()
    path.write_text(render(), encoding="utf-8")
    print(f"openapi: wrote {path}")


if __name__ == "__main__":
    main()
