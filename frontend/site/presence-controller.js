export function createPresenceController({
    api,
    url,
    csrfToken,
    documentRoot = document,
    windowObject = window,
    intervalMs = 30000,
}) {
    let started = false;
    let busy = false;
    let timer = null;
    let abortController = null;

    async function heartbeat() {
        if (!started || busy || documentRoot.hidden) return;
        busy = true;
        const controller = new windowObject.AbortController();
        abortController = controller;
        const timeout = windowObject.setTimeout(() => controller.abort(), 5000);
        try {
            await api.postJson(url, {}, csrfToken, {signal: controller.signal});
        } catch {
            // Presence is best-effort and must never interrupt the page.
        } finally {
            windowObject.clearTimeout(timeout);
            if (abortController === controller) abortController = null;
            busy = false;
        }
    }

    function schedule() {
        windowObject.clearInterval(timer);
        timer = null;
        if (started && !documentRoot.hidden) {
            void heartbeat();
            timer = windowObject.setInterval(heartbeat, intervalMs);
        }
    }

    function start() {
        if (started) return;
        started = true;
        documentRoot.addEventListener("visibilitychange", schedule);
        schedule();
    }

    function stop() {
        if (!started) return;
        started = false;
        documentRoot.removeEventListener("visibilitychange", schedule);
        abortController?.abort();
        abortController = null;
        windowObject.clearInterval(timer);
        timer = null;
    }

    return {start, stop, heartbeat};
}
