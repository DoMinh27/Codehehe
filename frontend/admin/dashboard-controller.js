function withManualRefresh(url) {
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}refresh=1`;
}


export function createDashboardController({
    root,
    renderer,
    fetchImpl = window.fetch.bind(window),
    documentRoot = document,
    windowObject = window,
    visibleDelay = Number(root?.dataset.refreshMs) || 15000,
    hiddenDelay = Number(root?.dataset.hiddenRefreshMs) || 60000,
    requestTimeout = Number(root?.dataset.requestTimeoutMs) || 5000,
}) {
    const stateUrl = root?.dataset.stateUrl;
    const refreshButton = root?.querySelector("#ops-refresh");
    let timeoutHandle = null;
    let requestTimeoutHandle = null;
    let inFlight = null;
    let activeAbortController = null;
    let stopped = true;

    function clearSchedule() {
        if (timeoutHandle !== null) {
            windowObject.clearTimeout(timeoutHandle);
            timeoutHandle = null;
        }
    }

    function schedule() {
        clearSchedule();
        if (stopped) {
            return;
        }
        const delay = documentRoot.hidden ? hiddenDelay : visibleDelay;
        timeoutHandle = windowObject.setTimeout(async () => {
            await refresh();
            schedule();
        }, delay);
    }

    async function requestState({manual = false} = {}) {
        if (inFlight) {
            return inFlight;
        }
        const abortController = new AbortController();
        activeAbortController = abortController;
        const url = manual ? withManualRefresh(stateUrl) : stateUrl;
        renderer.setRefreshing(true);
        requestTimeoutHandle = windowObject.setTimeout(
            () => abortController.abort(),
            requestTimeout,
        );
        inFlight = (async () => {
            try {
                const response = await fetchImpl(url, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                    signal: abortController.signal,
                });
                const contentType = response.headers?.get("content-type") || "";
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                if (!contentType.toLowerCase().includes("application/json")) {
                    throw new Error("Phản hồi không phải JSON.");
                }
                const payload = await response.json();
                renderer.render(payload);
                renderer.setFresh(payload.generated_at);
                return payload;
            } catch (error) {
                const message = error.name === "AbortError"
                    ? "Yêu cầu cập nhật đã quá thời gian chờ."
                    : (error.message || "Không thể cập nhật dashboard.");
                renderer.setStale(message);
                return null;
            } finally {
                windowObject.clearTimeout(requestTimeoutHandle);
                requestTimeoutHandle = null;
                activeAbortController = null;
                inFlight = null;
                renderer.setRefreshing(false);
            }
        })();
        return inFlight;
    }

    async function refresh(options) {
        return requestState(options);
    }

    async function handleManualRefresh() {
        clearSchedule();
        await refresh({manual: true});
        schedule();
    }

    function handleVisibilityChange() {
        schedule();
    }

    return {
        start(initialState) {
            if (!root || !stateUrl) {
                return;
            }
            stopped = false;
            renderer.render(initialState || {});
            renderer.setFresh(initialState?.generated_at);
            refreshButton?.addEventListener("click", handleManualRefresh);
            documentRoot.addEventListener("visibilitychange", handleVisibilityChange);
            schedule();
        },
        refresh,
        stop() {
            stopped = true;
            clearSchedule();
            if (requestTimeoutHandle !== null) {
                windowObject.clearTimeout(requestTimeoutHandle);
            }
            activeAbortController?.abort();
            refreshButton?.removeEventListener("click", handleManualRefresh);
            documentRoot.removeEventListener("visibilitychange", handleVisibilityChange);
        },
    };
}
