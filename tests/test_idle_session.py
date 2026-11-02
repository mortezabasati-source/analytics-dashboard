import re

import pytest
from playwright.sync_api import expect

WARNING_MS = 5 * 60 * 1000
TIMEOUT_MS = 10 * 60 * 1000


def open_dashboard(page, dashboard_url, *, simulated_time=True):
    sockets = []
    page.on("websocket", lambda ws: sockets.append(ws))
    if simulated_time:
        # Install before navigation, including before any app timers run.
        page.clock.install()
    with page.expect_websocket(lambda ws: "/_stcore/stream" in ws.url) as connection:
        page.goto(dashboard_url)
    expect(page.get_by_text("Dashboard run: 1", exact=True)).to_be_visible(timeout=30_000)
    expect(page.get_by_test_id("stException")).to_have_count(0)
    if simulated_time:
        # Leave enough headroom for trace capture and newly created iframes.
        # The trusted mouse event below establishes the test's idle baseline.
        page.clock.pause_at((page.evaluate("Date.now()") + 60_000) / 1000)
    page.mouse.move(10, 10)
    assert not connection.value.is_closed()
    return sockets


def warning(page):
    return page.get_by_role("dialog", name="Är du fortfarande kvar?")


def assert_expired(page, sockets):
    expect(page).to_have_url(re.compile(r"^blob:"))
    expect(page.get_by_role("heading", name="Sessionen har avslutats")).to_be_visible()
    assert sockets and all(ws.is_closed() for ws in sockets)


@pytest.mark.parametrize("activity", ["mouse", "keyboard", "click"])
def test_activity_keeps_websocket_open_for_twelve_minutes(page, dashboard_url, activity):
    sockets = open_dashboard(page, dashboard_url)
    for index in range(3):
        page.clock.fast_forward(4 * 60 * 1000)
        if activity == "mouse":
            page.mouse.move(20 + index * 10, 20)
        elif activity == "keyboard":
            page.keyboard.press("Shift")
        else:
            page.mouse.click(10, 10)
        expect(warning(page)).to_have_count(0)
        expect(page).to_have_url(dashboard_url)
        assert all(not ws.is_closed() for ws in sockets)


def test_warns_at_five_minutes_and_disconnects_at_ten(page, dashboard_url):
    sockets = open_dashboard(page, dashboard_url)
    page.clock.fast_forward(WARNING_MS - 1000)
    expect(warning(page)).to_have_count(0)
    page.clock.fast_forward(1000)
    expect(warning(page)).to_be_visible()
    expect(page.locator("#session-idle-countdown")).to_have_text("300")
    assert all(not ws.is_closed() for ws in sockets)
    page.clock.fast_forward(WARNING_MS - 1000)
    expect(warning(page)).to_be_visible()
    with sockets[0].expect_event("close"):
        page.clock.fast_forward(1000)
    assert_expired(page, sockets)

    # The terminal page has no Streamlit client and never reconnects itself.
    connection_count = len(sockets)
    page.clock.fast_forward(TIMEOUT_MS)
    assert_expired(page, sockets)
    assert len(sockets) == connection_count

    expect(page.get_by_role("link", name="Starta en ny session")).to_have_attribute(
        "href", dashboard_url,
    )
    with page.expect_websocket(lambda ws: "/_stcore/stream" in ws.url):
        page.get_by_role("link", name="Starta en ny session").click()
    expect(page).to_have_url(dashboard_url)
    expect(page.get_by_text("Dashboard run: 1", exact=True)).to_be_visible(timeout=30_000)
    expect(warning(page)).to_have_count(0)


def test_explicit_response_resets_idle_deadline(page, dashboard_url):
    sockets = open_dashboard(page, dashboard_url)
    page.clock.fast_forward(WARNING_MS)
    expect(warning(page)).to_be_visible()
    page.clock.fast_forward(4 * 60 * 1000)
    page.get_by_role("button", name="Fortsätt sessionen").click()
    expect(warning(page)).to_have_count(0)
    # Pass the original ten-minute deadline while the renewed session is active.
    page.clock.fast_forward(4 * 60 * 1000)
    expect(warning(page)).to_have_count(0)
    assert all(not ws.is_closed() for ws in sockets)
    page.clock.fast_forward(60 * 1000)
    expect(warning(page)).to_be_visible()


def test_mouse_motion_and_escape_do_not_dismiss_warning(page, dashboard_url):
    sockets = open_dashboard(page, dashboard_url)
    page.clock.fast_forward(WARNING_MS)
    expect(warning(page)).to_be_visible()
    page.mouse.move(40, 40)
    page.keyboard.press("Escape")
    expect(warning(page)).to_be_visible()
    with sockets[0].expect_event("close"):
        page.clock.fast_forward(WARNING_MS)
    assert_expired(page, sockets)


def test_rerun_and_synthetic_events_do_not_reset_deadline(page, dashboard_url):
    open_dashboard(page, dashboard_url)
    page.clock.fast_forward(4 * 60 * 1000)
    # Exercise a real Python rerun without trusted browser activity.
    page.get_by_role("button", name="Rerun dashboard").evaluate("button => button.click()")
    expect(page.get_by_text("Dashboard run: 2", exact=True)).to_be_visible()
    page.evaluate("document.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}))")
    page.clock.fast_forward(60 * 1000)
    expect(warning(page)).to_be_visible()
    expect(warning(page)).to_have_count(1)


def test_expiry_catches_up_after_suspended_timers(page, dashboard_url):
    sockets = open_dashboard(page, dashboard_url)
    # Advance wall time without firing timers, like a suspended browser process.
    now = page.evaluate("Date.now()")
    page.clock.set_system_time((now + TIMEOUT_MS + 1000) / 1000)
    # A returning user's first event must check expiry before resetting it.
    with sockets[0].expect_event("close"):
        page.mouse.move(50, 50)
    assert_expired(page, sockets)


def test_timeout_is_independent_for_each_tab(page, context, dashboard_url):
    idle_sockets = open_dashboard(page, dashboard_url)
    active_page = context.new_page()
    # Playwright's clock is shared across a browser context, just as wall time
    # is shared across tabs. Reuse it instead of installing a second clock.
    active_sockets = open_dashboard(active_page, dashboard_url, simulated_time=False)
    for index in range(2):
        page.clock.fast_forward(4 * 60 * 1000)
        active_page.mouse.move(30 + index * 10, 30)
    with idle_sockets[0].expect_event("close"):
        page.clock.fast_forward(2 * 60 * 1000)
    assert_expired(page, idle_sockets)
    expect(warning(active_page)).to_have_count(0)
    assert all(not ws.is_closed() for ws in active_sockets)
    active_page.close()


def test_idle_timeout_inside_cross_origin_installer(page, installer_url):
    """Match the GitHub Pages installer wrapping Cloud Run in an iframe."""
    sockets = []
    page.on("websocket", lambda socket: sockets.append(socket))
    page.clock.install()
    with page.expect_websocket(lambda socket: "/_stcore/stream" in socket.url):
        page.goto(installer_url)
    dashboard = page.frame(name="dashboard")
    assert dashboard is not None
    expect(dashboard.get_by_text("Dashboard run: 1", exact=True)).to_be_visible(timeout=30_000)
    page.clock.pause_at((dashboard.evaluate("Date.now()") + 60_000) / 1000)
    page.mouse.move(10, 10)

    page.clock.fast_forward(WARNING_MS)
    expect(dashboard.get_by_role("dialog", name="Är du fortfarande kvar?")).to_be_visible()
    with sockets[0].expect_event("close"):
        page.clock.fast_forward(TIMEOUT_MS - WARNING_MS)
    dashboard.wait_for_url(re.compile(r"^blob:"))
    expect(dashboard.get_by_role("heading", name="Sessionen har avslutats")).to_be_visible()
    expect(page).to_have_url(installer_url)
    assert sockets and all(socket.is_closed() for socket in sockets)


@pytest.mark.real_time
def test_disconnect_after_ten_actual_minutes(page, dashboard_url):
    sockets = open_dashboard(page, dashboard_url, simulated_time=False)
    expect(warning(page)).to_be_visible(timeout=WARNING_MS + 15_000)
    assert all(not ws.is_closed() for ws in sockets)
    expect(page).to_have_url(re.compile(r"^blob:"), timeout=WARNING_MS + 15_000)
    assert_expired(page, sockets)
