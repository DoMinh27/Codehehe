import {createPolling} from "../battle/polling.js";


export function createReviewController({
    api,
    stateUrl,
    csrfToken,
    renderer,
    documentRoot = document,
    windowObject = window,
}) {
    const list = documentRoot.getElementById("ai-review-list");
    let disposed = false;
    let listening = false;

    const polling = createPolling({
        refresh,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
        visibleDelay: 5000,
        hiddenDelay: 30000,
    });

    function syncPolling(payload) {
        if (payload.terminal) {
            polling.stop();
        } else if (!disposed) {
            polling.start({immediate: false});
        }
    }

    async function refresh() {
        if (disposed) {
            return;
        }
        try {
            const payload = await api.getJson(stateUrl);
            renderer.render(payload);
            syncPolling(payload);
        } catch (error) {
            renderer.showTemporaryError(
                error.message || "Chưa thể cập nhật phân tích AI.",
            );
        }
    }

    function handleVisibilityChange() {
        polling.reschedule();
    }

    async function handleClick(event) {
        const toggle = event.target.closest("[data-ai-review-toggle]");
        if (toggle && list.contains(toggle)) {
            const card = toggle.closest(".ai-review-card");
            const detail = card.querySelector(".ai-review-card__detail");
            detail.hidden = !detail.hidden;
            toggle.setAttribute("aria-expanded", detail.hidden ? "false" : "true");
            toggle.textContent = detail.hidden ? "Xem phân tích" : "Thu gọn";
            return;
        }

        const button = event.target.closest("[data-ai-review-request]");
        if (!button || button.disabled || !list.contains(button)) {
            return;
        }
        const requestUrl = button.dataset.aiReviewRequest;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        try {
            const payload = await api.post(requestUrl, csrfToken);
            renderer.render(payload);
            syncPolling(payload);
        } catch (error) {
            button.disabled = false;
            button.removeAttribute("aria-busy");
            renderer.showTemporaryError(
                error.message || "Chưa thể gửi yêu cầu phân tích AI.",
            );
        }
    }

    return {
        start(initialState) {
            disposed = false;
            renderer.render(initialState);
            if (!listening) {
                list.addEventListener("click", handleClick);
                documentRoot.addEventListener(
                    "visibilitychange",
                    handleVisibilityChange,
                );
                listening = true;
            }
            syncPolling(initialState);
        },
        stop,
        refresh,
    };

    function stop() {
        disposed = true;
        polling.stop();
        if (listening) {
            list.removeEventListener("click", handleClick);
            documentRoot.removeEventListener(
                "visibilitychange",
                handleVisibilityChange,
            );
            listening = false;
        }
    }
}
