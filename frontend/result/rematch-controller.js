import {createPolling} from "../battle/polling.js";

const STATUSES = new Set(["NONE", "PENDING", "ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"]);
const ACTIONS = new Set(["request", "accept", "decline", "cancel"]);

export function createRematchController({
    api, stateUrl, actionUrl, csrfToken,
    documentRoot = document, windowObject = window,
    navigate = (url) => windowObject.location.assign(url),
}) {
    const root = documentRoot.getElementById("rematch-controls");
    const notice = root.querySelector("[data-rematch-notice]");
    const errorNotice = root.querySelector("[data-rematch-error]");
    const openLink = root.querySelector("[data-rematch-open]");
    const refreshButton = root.querySelector("[data-rematch-refresh]");
    const buttons = [...root.querySelectorAll("[data-rematch-action]")];
    let state = null;
    let disposed = true;
    let busy = false;
    let cancelRequest = null;
    let redirectWhenAccepted = false;
    let redirected = false;
    let generation = 0;

    const polling = createPolling({
        refresh,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
        visibleDelay: 5000, hiddenDelay: 30000,
    });

    function checkState(payload) {
        if (!payload || !STATUSES.has(payload.status)
            || !Array.isArray(payload.actions) || payload.actions.some((a) => !ACTIONS.has(a))
            || typeof payload.terminal !== "boolean" || typeof payload.is_requester !== "boolean") {
            throw new Error("Máy chủ trả về trạng thái tái đấu không hợp lệ");
        }
        return payload;
    }

    function roomUrl() {
        const value = state?.room_url;
        if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) return null;
        const url = new URL(value, windowObject.location.href);
        return url.origin === windowObject.location.origin ? url.href : null;
    }

    function render() {
        if (!state) return;
        const remaining = Math.max(0, Math.ceil((Date.parse(state.expires_at) - Date.parse(state.server_time)) / 1000));
        const messages = {
            NONE: "Mời chơi lại",
            PENDING: state.is_requester
                ? `Đã gửi lời mời (lời mời sẽ hết hạn sau ${remaining} giây)`
                : `${state.requester_name} mời bạn tái đấu (lời mời hết hạn sau ${remaining} giây)`,
            ACCEPTED: "Hai người đã đồng ý. Phòng tái đấu đã được tạo",
            DECLINED: "Lời mời đã bị từ chối",
            CANCELLED: "Lời mời đã được hủy",
            EXPIRED: "Lời mời đã hết hạn. Mỗi trận chỉ có một lời mời",
        };
        let message = state.unavailable_reason || messages[state.status];
        if (state.status === "ACCEPTED" && !state.room_url) {
            message = state.new_match_status === "CANCELLED"
                ? "Phòng tái đấu đã bị hủy"
                : "Bạn không còn trong phòng tái đấu";
        }
        if (notice.textContent !== message) notice.textContent = message;
        root.setAttribute("aria-busy", String(busy));
        for (const button of buttons) {
            button.hidden = !state.actions.includes(button.dataset.rematchAction);
            button.disabled = busy || button.hidden;
        }
        refreshButton.disabled = busy;
        const url = roomUrl();
        openLink.hidden = !url;
        if (url) {
            openLink.href = url;
            openLink.textContent = state.new_match_status === "FINISHED" ? "Xem kết quả tái đấu" : "Vào trận tái đấu";
        } else openLink.removeAttribute("href");
    }

    function applyState(payload) {
        state = checkState(payload);
        render();
        if (state.terminal) polling.stop();
        const url = roomUrl();
        if (redirectWhenAccepted && !redirected && state.status === "ACCEPTED" && url
            && ["WAITING", "PLAYING"].includes(state.new_match_status)) {
            redirected = true;
            navigate(url);
        }
    }

    async function withDeadline(operation) {
        const controller = new windowObject.AbortController();
        let timer;
        let cancel;
        const timeout = new Promise((resolve, reject) => {
            cancel = () => {
                controller.abort();
                reject(new Error("Yêu cầu đã bị hủy"));
            };
            cancelRequest = cancel;
            timer = windowObject.setTimeout(() => {
                controller.abort();
                reject(new Error("Yêu cầu quá 10 giây. Trạng thái có thể đã thay đổi; hãy cập nhật lại"));
            }, 10000);
        });
        try {
            return await Promise.race([operation(controller.signal), timeout]);
        } finally {
            windowObject.clearTimeout(timer);
            if (cancelRequest === cancel) cancelRequest = null;
        }
    }

    async function run(action = null) {
        if (disposed || busy) return;
        const requestGeneration = generation;
        const focusedElement = documentRoot.activeElement;
        const hadFocus = root.contains(focusedElement);
        busy = true;
        errorNotice.textContent = "";
        render();
        try {
            const payload = await withDeadline((signal) => action
                ? api.postJson(actionUrl, {action}, csrfToken, {signal})
                : api.getJson(stateUrl, {signal}));
            if (!disposed && generation === requestGeneration) applyState(payload);
        } catch (error) {
            if (!disposed && generation === requestGeneration) errorNotice.textContent = error.message || "Chưa thể cập nhật tái đấu. Vui lòng thử lại";
        } finally {
            if (!disposed && generation === requestGeneration) {
                busy = false;
                render();
                if (hadFocus && [documentRoot.body, focusedElement].includes(documentRoot.activeElement)) {
                    if (!focusedElement.hidden && !focusedElement.disabled) {
                        focusedElement.focus({preventScroll: true});
                    } else {
                        notice.tabIndex = -1;
                        notice.focus({preventScroll: true});
                    }
                }
                if (state && !state.terminal) polling.start({immediate: false});
            }
        }
    }

    function refresh() { return run(); }

    function handleClick(event) {
        const refreshTarget = event.target.closest("[data-rematch-refresh]");
        if (refreshTarget && root.contains(refreshTarget)) {
            void refresh();
            return;
        }
        const button = event.target.closest("[data-rematch-action]");
        if (!button || !root.contains(button) || button.disabled || disposed || busy) return;
        const action = button.dataset.rematchAction;
        if (!state.actions.includes(action)) return;
        if (action === "request" || action === "accept") redirectWhenAccepted = true;
        if (action === "cancel" || action === "decline") redirectWhenAccepted = false;
        void run(action);
    }

    function handleVisibility() { polling.reschedule(); }
    function handlePageHide() { stop({resumeOnShow: true}); }
    function handlePageShow(event) {
        if (event.persisted && state) {
            start(state);
            void refresh();
        }
    }
    function start(initialState) {
        if (!disposed) return;
        disposed = false;
        redirected = false;
        redirectWhenAccepted = initialState.status === "PENDING" && initialState.is_requester;
        applyState(initialState);
        root.addEventListener("click", handleClick);
        documentRoot.addEventListener("visibilitychange", handleVisibility);
        windowObject.addEventListener("pagehide", handlePageHide);
        windowObject.addEventListener("pageshow", handlePageShow);
        if (!state.terminal) polling.start({immediate: false});
    }
    function stop({resumeOnShow = false} = {}) {
        disposed = true;
        generation += 1;
        busy = false;
        polling.stop();
        cancelRequest?.();
        root.removeEventListener("click", handleClick);
        documentRoot.removeEventListener("visibilitychange", handleVisibility);
        windowObject.removeEventListener("pagehide", handlePageHide);
        if (!resumeOnShow) windowObject.removeEventListener("pageshow", handlePageShow);
    }
    return {start, stop, refresh};
}
