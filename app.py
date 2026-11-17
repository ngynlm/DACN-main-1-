from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


ROOT = Path(__file__).resolve().parent
CONSOLE = ROOT / "console"
FRONTEND_URL = "http://127.0.0.1:5173/login?forceLogin=1"
BACKEND_HEALTH_URL = "http://127.0.0.1:8088/api/auth/status"
FRONTEND_HEALTH_URL = "http://127.0.0.1:5173/"

BACKEND_COMMAND = (
    "from qwenpaw.cli.main import cli; "
    "cli.main(args=['app', '--host', '127.0.0.1', '--port', '8088'], "
    "standalone_mode=False)"
)


def _wait_for_url(url: str, process: subprocess.Popen, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"Startup process exited with code {exit_code}: {url}",
            )
        try:
            with urlopen(url, timeout=1):
                return
        except (OSError, URLError):
            time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {url}")


def _start_frontend(env: dict[str, str]) -> subprocess.Popen:
    node = shutil.which("node.exe") or shutil.which("node")
    vite_cli = CONSOLE / "node_modules" / "vite" / "bin" / "vite.js"
    if not node:
        raise RuntimeError("Node.js is missing. Install Node.js first.")
    if not vite_cli.is_file():
        raise RuntimeError(
            "Console dependencies are missing. Run 'npm ci' in console/ first.",
        )

    return subprocess.Popen(
        [node, str(vite_cli), "--host", "127.0.0.1", "--strictPort"],
        cwd=CONSOLE,
        env=env,
    )


def _check_port_available(port: int, service: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        try:
            server.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"Port {port} is already in use. Stop the existing {service} "
                "process and try again.",
            ) from exc


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> None:
    env = os.environ.copy()
    env["QWENPAW_AUTH_ENABLED"] = "true"
    source_path = str(ROOT / "src")
    existing_python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_path, existing_python_path) if part
    )
    frontend_env = env.copy()
    frontend_env["TOKEN"] = ""

    backend: subprocess.Popen | None = None
    frontend: subprocess.Popen | None = None
    try:
        _check_port_available(8088, "QwenPaw backend")
        _check_port_available(5173, "Console dev server")
        backend = subprocess.Popen(
            [sys.executable, "-c", BACKEND_COMMAND],
            cwd=ROOT,
            env=env,
        )
        frontend = _start_frontend(frontend_env)
        _wait_for_url(BACKEND_HEALTH_URL, backend)
        _wait_for_url(FRONTEND_HEALTH_URL, frontend)

        print(f"QwenPaw is ready: {FRONTEND_URL}")
        print("Press Ctrl+C to stop the local app.")
        webbrowser.open(FRONTEND_URL)

        while True:
            for name, process in (("backend", backend), ("Console", frontend)):
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"The {name} process exited with code {exit_code}.",
                    )
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping QwenPaw...")
    except (RuntimeError, TimeoutError) as exc:
        print(f"QwenPaw could not start: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        _stop_process(frontend)
        _stop_process(backend)


if __name__ == "__main__":
    main()
