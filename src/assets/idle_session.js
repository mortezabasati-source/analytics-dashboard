(config) => {
    "use strict";

    // This script executes in the app window, not in the component iframe.
    // Preserve the deadline and install listeners only once across reruns.
    const key = "__streamlitIdleSession";
    if (window[key]) {
        window[key].checkDeadline();
        return;
    }

    let lastActivity = Date.now();
    let warning = null;
    let previousFocus = null;
    let expired = false;
    let interval;
    const restartUrl = window.location.href;
    const activityEvents = [
        "mousemove", "pointerdown", "click", "keydown", "touchstart", "wheel", "scroll", "input",
    ];

    function expire() {
        if (expired) return;
        expired = true;
        window.clearInterval(interval);
        for (const event of activityEvents) {
            document.removeEventListener(event, onActivity, true);
        }
        document.removeEventListener("visibilitychange", checkDeadline);
        window.removeEventListener("pageshow", checkDeadline);

        const page = new DOMParser().parseFromString(config.expiredPage, "text/html");
        page.getElementById("restart-session").setAttribute("href", restartUrl);
        const url = URL.createObjectURL(new Blob(
            ["<!doctype html>\n", page.documentElement.outerHTML],
            {type: "text/html;charset=utf-8"},
        ));
        // A real navigation unloads Streamlit, closes its WebSocket, and removes
        // its reconnect loop. The destination makes no requests to Cloud Run.
        window.location.replace(url);
    }

    function resume(event) {
        if (!event.isTrusted || checkDeadline()) return;
        lastActivity = Date.now();
        warning.close();
        warning.remove();
        warning = null;
        if (previousFocus && previousFocus.isConnected) previousFocus.focus();
    }

    function showWarning() {
        previousFocus = document.activeElement;
        warning = document.createElement("dialog");
        warning.id = "session-idle-warning";
        warning.setAttribute("aria-labelledby", "session-idle-heading");
        warning.setAttribute("aria-describedby", "session-idle-description");
        warning.innerHTML = `
            <style>
                #session-idle-warning {
                    color: #15233b; background: #fff; border: 0; border-radius: 12px;
                    padding: 28px; max-width: 440px; width: calc(100% - 48px);
                    box-sizing: border-box; font: 16px/1.6 system-ui, sans-serif;
                    box-shadow: 0 16px 64px #0004;
                }
                #session-idle-warning::backdrop { background: #0008; }
                #session-idle-warning h2 { font-size: 24px; margin: 0 0 12px; }
                #session-idle-warning button {
                    background: #1759a8; color: #fff; border: 0; border-radius: 6px;
                    padding: 12px 18px; cursor: pointer; font: inherit;
                }
                #session-idle-warning button:focus-visible { outline: 3px solid #e29a16; }
            </style>
            <h2 id="session-idle-heading">Är du fortfarande kvar?</h2>
            <p id="session-idle-description">
                Du har varit inaktiv. Sessionen avslutas om
                <output id="session-idle-countdown"></output> sekunder.
                Klicka på knappen för att fortsätta.
            </p>
            <button type="button">Fortsätt sessionen</button>
        `;
        // Escape must not hide the warning without resetting the deadline.
        warning.addEventListener("cancel", (event) => event.preventDefault());
        warning.querySelector("button").addEventListener("click", resume);
        document.body.appendChild(warning);
        warning.showModal();
    }

    function checkDeadline() {
        if (expired) return true;
        // Absolute elapsed time catches up after background timer throttling
        // or laptop sleep; a late activity event must not revive an expired tab.
        const elapsed = Date.now() - lastActivity;
        if (elapsed >= config.timeoutMs) {
            expire();
            return true;
        }
        if (elapsed >= config.warningMs) {
            if (!warning) showWarning();
            warning.querySelector("output").textContent = String(
                Math.ceil((config.timeoutMs - elapsed) / 1000),
            );
        }
        return false;
    }

    function onActivity(event) {
        if (!event.isTrusted || checkDeadline()) return;
        // Once warned, require an explicit response to the modal.
        if (!warning) lastActivity = Date.now();
    }

    for (const event of activityEvents) {
        document.addEventListener(event, onActivity, {capture: true, passive: true});
    }
    // Focusing/returning to a tab checks expiry; it is not user activity.
    document.addEventListener("visibilitychange", checkDeadline);
    window.addEventListener("pageshow", checkDeadline);
    interval = window.setInterval(checkDeadline, 1000);
    window[key] = {checkDeadline};
}
