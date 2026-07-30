import {createPolling} from "../battle/polling.js";


export function createReviewController({
    api,
    stateUrl,
    renderer,
    documentRoot = document,
    windowObject = window,
}) {
    let stopped = false;

    const polling = createPolling({
        refresh: refresh,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
        visibleDelay: 5000,
        hiddenDelay: 30000,
    });

    async function refresh() {
        if (stopped) {
            return;
        }
        try {
            const payload = await api.getJson(stateUrl);
            renderer.render(payload);
            if (payload.terminal) {
                stop();
            }
        } catch (error) {
            renderer.showTemporaryError(
                error.message || "Chưa thể cập nhật phân tích AI.",
            );
        }
    }

    function handleVisibilityChange() {
        polling.reschedule();
    }

    return {
        start(initialState) {
            stopped = false;
            renderer.render(initialState);
            if (!initialState.terminal) {
                polling.start({immediate: false});
                documentRoot.addEventListener(
                    "visibilitychange",
                    handleVisibilityChange,
                );
            }
        },
        stop,
        refresh,
    };

    function stop() {
        stopped = true;
        polling.stop();
        documentRoot.removeEventListener(
            "visibilitychange",
            handleVisibilityChange,
        );
    }
}
