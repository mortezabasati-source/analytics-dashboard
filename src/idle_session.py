"""Install a browser-side idle timeout without using Streamlit internals."""

import json
import os
from functools import lru_cache
from pathlib import Path

import streamlit.components.v1 as components


@lru_cache(maxsize=1)
def _assets():
    asset_dir = Path(__file__).with_name("assets")
    return (
        (asset_dir / "idle_session.js").read_text(encoding="utf-8"),
        (asset_dir / "session_expired.html").read_text(encoding="utf-8"),
    )


def install_idle_session_timeout():
    """Warn at five idle minutes; leave Streamlit at ten, per browser tab.

    Environment settings are positive integer seconds, measured from the last
    activity. The timeout must be strictly greater than the warning threshold.
    """
    try:
        warning = int(os.environ.get("SESSION_IDLE_WARNING_SECONDS", "300"))
        timeout = int(os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS", "600"))
    except ValueError as exc:
        raise ValueError("Session idle thresholds must be integer seconds") from exc
    if not 0 < warning < timeout:
        raise ValueError("Session idle thresholds must satisfy 0 < warning < timeout")

    javascript, expired_page = _assets()
    config = json.dumps({
        "warningMs": warning * 1000,
        "timeoutMs": timeout * 1000,
        "expiredPage": expired_page,
    })
    # Run in the parent document so timers survive iframe replacement on reruns
    # and navigation does not inherit the component's sandbox restrictions.
    # Escape '<' so embedded HTML cannot terminate this script element.
    payload = json.dumps(f"({javascript})({config});").replace("<", "\\u003c")
    components.html(
        "<script>"
        "const script = window.parent.document.createElement('script');"
        f"script.textContent = {payload};"
        "window.parent.document.head.appendChild(script);"
        "script.remove();"
        "</script>",
        height=0,
        width=0,
    )
