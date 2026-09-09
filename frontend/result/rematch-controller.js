const STATUSES = new Set(["NONE", "PENDING", "ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"]);
const ACTIONS = new Set(["request", "accept", "decline", "cancel"]);


export function createRematchController({
    api,
    actionUrl,
    csrfToken,
    documentRoot = document,
    windowObject = window,
}) {
    const root = documentRoot.getElementById("rematch-controls");
    if (!root) return null;
    const button = root.querySelector("[data-rematch-request]");
    const status = root.querySelector("[data-rematch-status]");
    let state = null;
    let started = false;
    let busy = false;
    let abortController = null;
    let actionError = "";

    function validateState(payload) {
        if (!payload || !STATUSES.has(payload.status) || !Array.isArray(payload.actions)
            || payload.actions.some((action) => !ACTIONS.has(action))
            || typeof payload.is_requester !== "boolean") {
            throw new Error("Máy chủ trả về trạng thái tái đấu không hợp lệ");
        }
        return payload;
    }

    function render() {
        if (!state) return;
        const isOutgoing = state.status === "PENDING" && state.is_requester;
        const isIncoming = state.status === "PENDING" && !state.is_requester;
        button.hidden = !["NONE", "PENDING"].includes(state.status);
        button.disabled = busy || !state.actions.includes("request");
        button.textContent = isOutgoing
            ? "Đã gửi lời mời"
            : (isIncoming ? "Có lời mời đang chờ" : "Mời tái đấu");
        root.setAttribute("aria-busy", String(busy));
        if (busy) {
            status.textContent = "Đang gửi lời mời";
        } else if (actionError) {
            status.textContent = actionError;
        } else if (state.unavailable_reason && state.status === "NONE") {
            status.textContent = state.unavailable_reason.replace(/\.$/, "");
        } else if (isOutgoing) {
            status.textContent = "Theo dõi phản hồi trong Thông báo";
        } else if (isIncoming) {
            status.textContent = "Mở Thông báo để phản hồi";
        } else {
            status.textContent = "";
        }
    }

    async function requestRematch() {
        if (!started || busy || button.disabled || !state.actions.includes("request")) return;
        busy = true;
        actionError = "";
        render();
        const controller = new windowObject.AbortController();
        abortController = controller;
        const timer = windowObject.setTimeout(() => controller.abort(), 5000);
        try {
            state = validateState(await api.postJson(
                actionUrl,
                {action: "request"},
                csrfToken,
                {signal: controller.signal},
            ));
            windowObject.dispatchEvent(new windowObject.CustomEvent(
                "social:notifications-refresh",
            ));
        } catch (error) {
            actionError = error?.message || "Chưa thể gửi lời mời tái đấu";
        } finally {
            windowObject.clearTimeout(timer);
            if (abortController === controller) abortController = null;
            busy = false;
            render();
        }
    }

    function start(initialState) {
        if (started) return;
        state = validateState(initialState);
        started = true;
        button.addEventListener("click", requestRematch);
        render();
    }

    function stop() {
        if (!started) return;
        started = false;
        abortController?.abort();
        button.removeEventListener("click", requestRematch);
    }

    return {start, stop};
}
