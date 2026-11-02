import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
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


@pytest.fixture
def installer_url(dashboard_url):
    """Serve the installer from a real second origin, like GitHub Pages.

    A fulfilled Playwright route has no server IP and can trigger Chromium's
    private-network checks when it embeds a real loopback server.
    """
    body = (
        '<!doctype html><html><head><title>Installer</title></head>'
        '<body style="margin:0">'
        f'<iframe name="dashboard" src="{dashboard_url}" '
        'style="width:100vw;height:100vh;border:0"></iframe>'
        '</body></html>'
    ).encode("utf-8")

    class InstallerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), InstallerHandler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            worker.join(timeout=5)
