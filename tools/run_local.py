import argparse
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def port_in_use(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.3)
            if probe.connect_ex((host, port)) == 0:
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run claims_api, agent_app and the web UI together."
    )
    parser.add_argument(
        "--fake", action="store_true", help="use the rule-based model and keyword search"
    )
    parser.add_argument(
        "--uv", default=os.environ.get("UV", "uv"), help="path to the uv executable"
    )
    parser.add_argument("--claims-port", type=int, default=8001)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=5273)
    args = parser.parse_args()

    busy = [port for port in (args.claims_port, args.api_port, args.ui_port) if port_in_use(port)]
    if busy:
        print(
            f"run: port(s) {', '.join(map(str, busy))} already in use by another program. "
            "Stop it or pass --claims-port, --api-port or --ui-port.",
            file=sys.stderr,
        )
        return 2

    if not args.fake:
        missing = [n for n in ("AGENT_GATEWAY_URL", "RAG_SEARCH_ENDPOINT") if not os.environ.get(n)]
        if not any(n.startswith("GATEWAY_KEY_") and os.environ[n] for n in os.environ):
            missing.append("GATEWAY_KEY_<COUNTRY>")
        if missing:
            print(
                f"run: {', '.join(missing)} not set. Export them (see MANUAL.md) "
                "or use `make run FAKE=1` for the offline fake model.",
                file=sys.stderr,
            )
            return 2

    env = {
        **os.environ,
        "APPROVAL_SIGNING_KEY": os.environ.get("APPROVAL_SIGNING_KEY") or secrets.token_urlsafe(32),
    }
    api_env = {
        **env,
        "CLAIMS_API_URL": f"http://localhost:{args.claims_port}",
        "AGENT_CORS_ORIGINS": f"http://localhost:{args.ui_port}",
    }
    if args.fake:
        api_env["AGENT_FAKE_MODE"] = "1"

    commands = {
        "claims_api": (
            [
                args.uv,
                "run",
                "--package",
                "claims_api",
                "uvicorn",
                "claims_api.app:create_app",
                "--factory",
                "--port",
                str(args.claims_port),
            ],
            env,
        ),
        "agent_app": (
            [
                args.uv,
                "run",
                "--package",
                "agent_app",
                "uvicorn",
                "agent_app.main:create_app",
                "--factory",
                "--port",
                str(args.api_port),
            ],
            api_env,
        ),
        "web_ui": (
            ["pnpm", "-C", "components/web_ui", "exec", "vite", "--port", str(args.ui_port)],
            env,
        ),
    }
    children = {
        name: subprocess.Popen(command, cwd=ROOT, env=child_env)
        for name, (command, child_env) in commands.items()
    }
    mode = "fake model" if args.fake else "live Azure"
    print(
        f"\nrun: {mode}. Open http://localhost:{args.ui_port}  (API on :{args.api_port}, "
        f"claims system on :{args.claims_port}). Ctrl-C stops everything.\n"
    )

    def stop(*_: object) -> None:
        for child in children.values():
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    exit_code = 0
    while True:
        for name, child in children.items():
            code = child.poll()
            if code is not None:
                if exit_code == 0 and code != 0 and not _stopping(children):
                    print(f"run: {name} exited with {code}", file=sys.stderr)
                    exit_code = code
                stop()
        if all(child.poll() is not None for child in children.values()):
            return exit_code
        time.sleep(0.5)


def _stopping(children: dict[str, subprocess.Popen[bytes]]) -> bool:
    return any(child.returncode in (-signal.SIGTERM, -signal.SIGINT) for child in children.values())


if __name__ == "__main__":
    raise SystemExit(main())
