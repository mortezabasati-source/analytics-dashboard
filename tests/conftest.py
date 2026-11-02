import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-time", action="store_true", default=False,
        help="Also run the ten-minute idle test using real browser time",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-time"):
        return
    for item in items:
        if "real_time" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="Use --run-real-time (takes ten minutes)"))


@pytest.fixture(scope="session")
def dashboard_url(tmp_path_factory):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    # A base path and query string also exercise the restart URL behind a proxy.
    base_url = f"http://127.0.0.1:{port}/dashboard"
    env = os.environ.copy()
    env.update({
        "SESSION_IDLE_WARNING_SECONDS": "300",
        "SESSION_IDLE_TIMEOUT_SECONDS": "600",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    })
    log_path = tmp_path_factory.mktemp("streamlit") / "server.log"
    with log_path.open("w+", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run",
                str(ROOT / "tests" / "fixtures" / "dashboard.py"),
                f"--server.port={port}", "--server.address=127.0.0.1",
                "--server.headless=true", "--server.fileWatcherType=none",
                "--server.baseUrlPath=dashboard",
            ],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    break
                try:
                    with urlopen(f"{base_url}/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            yield f"{base_url}/?report=sample"
                            return
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            log.seek(0)
            pytest.fail(f"Streamlit did not start:\n{log.read()}")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
