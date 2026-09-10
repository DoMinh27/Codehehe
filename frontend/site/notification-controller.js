import {createPolling} from "../battle/polling.js";


const ITEM_KINDS = new Set(["REMATCH", "FRIEND_REQUEST"]);
const DIRECTIONS = new Set(["INCOMING", "OUTGOING"]);
const ACTION_LABELS = new Map([
    ["ACCEPT", "Đồng ý"],
    ["DECLINE", "Từ chối"],
    ["CANCEL", "Hủy lời mời"],
]);
const SEEN_STORAGE_KEY = "codehehe.notification.seen.v1";


function isSafeRelativeUrl(value, windowObject) {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
        return false;
    }
    try {
        return new URL(value, windowObject.location.href).origin === windowObject.location.origin;
    } catch {
        return false;
    }
}


function validateState(payload, windowObject) {
    if (!payload || payload.version !== 1 || typeof payload.server_time !== "string"
        || !Number.isInteger(payload.incoming_count) || payload.incoming_count < 0
        || !Array.isArray(payload.items) || payload.items.length > 20) {
        throw new Error("Máy chủ trả về thông báo không hợp lệ");
    }
    for (const item of payload.items) {
        if (!item || typeof item.key !== "string" || !ITEM_KINDS.has(item.kind)
            || !DIRECTIONS.has(item.direction) || typeof item.created_at !== "string"
            || typeof item.expires_at !== "string" || !item.actor
            || typeof item.actor.username !== "string" || typeof item.actor.initial !== "string"
            || !item.context
            || !isSafeRelativeUrl(item.context_url, windowObject)
            || !Array.isArray(item.actions)) {
            throw new Error("Máy chủ trả về thông báo không hợp lệ");
        }
        if (item.kind === "REMATCH"
            && (typeof item.context.match_code !== "string"
                || typeof item.context.score !== "string")) {
            throw new Error("Máy chủ trả về thông báo không hợp lệ");
        }
        for (const action of item.actions) {
            if (!action || !ACTION_LABELS.has(action.code)
                || !isSafeRelativeUrl(action.url, windowObject)) {
                throw new Error("Máy chủ trả về hành động không hợp lệ");
            }
        }
    }
    if (payload.more_url !== null && payload.more_url !== undefined
        && !isSafeRelativeUrl(payload.more_url, windowObject)) {
        throw new Error("Máy chủ trả về liên kết không hợp lệ");
    }
    return payload;
}


function readSeen(storage) {
    try {
        const value = JSON.parse(storage.getItem(SEEN_STORAGE_KEY) || "[]");
        return new Set(Array.isArray(value) ? value.filter((key) => typeof key === "string") : []);
    } catch {
        return new Set();
    }
}


function writeSeen(storage, seen) {
    try {
        storage.setItem(SEEN_STORAGE_KEY, JSON.stringify([...seen].slice(-100)));
    } catch {
        // Notifications still work when sessionStorage is unavailable.
    }
}


export function createNotificationController({
    api,
    stateUrl,
    csrfToken,
    documentRoot = document,
    windowObject = window,
    navigate = (url) => windowObject.location.assign(url),
    visibleDelay = 5000,
    hiddenDelay = 30000,
}) {
    const root = documentRoot.querySelector("[data-notification-center]");
    if (!root) return null;

    const trigger = root.querySelector("[data-notification-trigger]");
    const panel = root.querySelector("[data-notification-panel]");
    const badge = root.querySelector("[data-notification-badge]");
    const list = root.querySelector("[data-notification-list]");
    const empty = root.querySelector("[data-notification-empty]");
    const more = root.querySelector("[data-notification-more]");
    const status = root.querySelector("[data-notification-status]");
    const toastStack = documentRoot.querySelector("[data-notification-toasts]");
    const seen = readSeen(windowObject.sessionStorage);
    let started = false;
    let busy = false;
    let generation = 0;
    let abortController = null;

    const polling = createPolling({
        refresh,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
        visibleDelay,
        hiddenDelay,
    });

    function safeNavigationUrl(value) {
        if (!isSafeRelativeUrl(value, windowObject)) return null;
        return new URL(value, windowObject.location.href).href;
    }

    function setOpen(open, {restoreFocus = false} = {}) {
        panel.hidden = !open;
        trigger.setAttribute("aria-expanded", String(open));
        if (!open && restoreFocus) trigger.focus({preventScroll: true});
    }

    function countdown(item, serverTime) {
        const seconds = Math.max(
            0,
            Math.ceil((Date.parse(item.expires_at) - Date.parse(serverTime)) / 1000),
        );
        if (seconds >= 86400) return `Còn ${Math.ceil(seconds / 86400)} ngày`;
        if (seconds >= 3600) return `Còn ${Math.ceil(seconds / 3600)} giờ`;
        if (seconds >= 60) return `Còn ${Math.ceil(seconds / 60)} phút`;
        return `Còn ${seconds} giây`;
    }

    function makeElement(tagName, className, text = "") {
        const element = documentRoot.createElement(tagName);
        if (className) element.className = className;
        element.textContent = text;
        return element;
    }

    function showToast(item) {
        if (!toastStack || item.direction !== "INCOMING" || seen.has(item.key)) return;
        seen.add(item.key);
        writeSeen(windowObject.sessionStorage, seen);
        const toastText = item.kind === "FRIEND_REQUEST"
            ? `${item.actor.username} vừa gửi lời mời kết bạn`
            : `${item.actor.username} vừa gửi lời mời tái đấu`;
        const toast = makeElement(
            "div",
            "notification-toast",
            toastText,
        );
        toastStack.prepend(toast);
        windowObject.setTimeout(() => toast.classList.add("notification-toast--leaving"), 4500);
        windowObject.setTimeout(() => toast.remove(), 4800);
    }

    function renderItem(item, serverTime) {
        const article = makeElement("article", "notification-item");
        article.dataset.notificationKey = item.key;
        const avatar = makeElement("span", "avatar notification-item__avatar", item.actor.initial);
        avatar.setAttribute("aria-hidden", "true");
        const body = makeElement("div", "notification-item__body");
        const titleText = item.kind === "FRIEND_REQUEST"
            ? (item.direction === "INCOMING"
                ? `${item.actor.username} muốn kết bạn`
                : `Đang chờ ${item.actor.username} đồng ý kết bạn`)
            : (item.direction === "INCOMING"
                ? `${item.actor.username} mời bạn tái đấu`
                : `Đang chờ ${item.actor.username} phản hồi`);
        const title = makeElement(
            "p",
            "notification-item__title",
            titleText,
        );
        const expiry = makeElement("p", "notification-item__time", countdown(item, serverTime));
        body.append(title);
        if (item.kind === "REMATCH") {
            body.append(makeElement(
                "p",
                "notification-item__detail",
                `Trận ${item.context.match_code} · ${item.context.score}`,
            ));
        }
        body.append(expiry);
        if (item.unavailable_reason) {
            body.append(makeElement("p", "notification-item__unavailable", item.unavailable_reason));
        }
        const actions = makeElement("div", "notification-item__actions");
        for (const action of item.actions) {
            const button = makeElement("button", "button button-small", ACTION_LABELS.get(action.code));
            button.type = "button";
            button.classList.add(action.code === "ACCEPT" ? "button-primary" : "button-secondary");
            button.dataset.notificationAction = action.code;
            button.dataset.notificationActionUrl = action.url;
            button.addEventListener("click", () => void runAction(button));
            actions.append(button);
        }
        const contextLink = makeElement(
            "a",
            "notification-item__context-link",
            item.kind === "FRIEND_REQUEST" ? "Xem bạn bè" : "Xem kết quả",
        );
        contextLink.href = item.context_url;
        actions.append(contextLink);
        body.append(actions);
        article.append(avatar, body);
        return article;
    }

    function render(payload) {
        const focusedElement = documentRoot.activeElement;
        const focusedItem = focusedElement?.closest?.("[data-notification-key]");
        const focusedKey = focusedItem?.dataset.notificationKey;
        const focusedAction = focusedElement?.dataset?.notificationAction;
        const focusedContextLink = focusedElement?.classList?.contains(
            "notification-item__context-link",
        );
        badge.textContent = payload.incoming_count > 99 ? "99+" : String(payload.incoming_count);
        badge.hidden = payload.incoming_count === 0;
        trigger.setAttribute(
            "aria-label",
            payload.incoming_count
                ? `Thông báo, ${payload.incoming_count} yêu cầu đang chờ`
                : "Thông báo",
        );
        const fragment = documentRoot.createDocumentFragment();
        for (const item of payload.items) {
            fragment.append(renderItem(item, payload.server_time));
            showToast(item);
        }
        list.replaceChildren(fragment);
        empty.hidden = payload.items.length !== 0;
        if (more) {
            const moreUrl = safeNavigationUrl(payload.more_url);
            more.hidden = !moreUrl;
            if (moreUrl) more.href = moreUrl;
        }
        status.textContent = "";
        status.hidden = true;
        if (focusedKey && !panel.hidden) {
            const replacement = [...list.querySelectorAll("[data-notification-key]")]
                .find((item) => item.dataset.notificationKey === focusedKey);
            const focusTarget = focusedAction
                ? [...(replacement?.querySelectorAll("[data-notification-action]") || [])]
                    .find((item) => item.dataset.notificationAction === focusedAction)
                : (focusedContextLink
                    ? replacement?.querySelector(".notification-item__context-link")
                    : null);
            focusTarget?.focus({preventScroll: true});
        }
    }

    async function withDeadline(operation) {
        const controller = new windowObject.AbortController();
        abortController = controller;
        const timer = windowObject.setTimeout(() => controller.abort(), 5000);
        try {
            return await operation(controller.signal);
        } finally {
            windowObject.clearTimeout(timer);
            if (abortController === controller) abortController = null;
        }
    }

    async function refresh() {
        if (!started || busy) return;
        const requestGeneration = generation;
        busy = true;
        try {
            const payload = await withDeadline((signal) => api.getJson(stateUrl, {signal}));
            if (started && generation === requestGeneration) {
                render(validateState(payload, windowObject));
            }
        } catch {
            if (started && generation === requestGeneration) {
                status.textContent = "Dữ liệu có thể đã cũ";
                status.hidden = false;
            }
        } finally {
            if (generation === requestGeneration) busy = false;
        }
    }

    async function runAction(button) {
        if (!started || busy || button.disabled) return;
        const code = button.dataset.notificationAction;
        const url = button.dataset.notificationActionUrl;
        if (!ACTION_LABELS.has(code) || !isSafeRelativeUrl(url, windowObject)) return;
        const requestGeneration = generation;
        busy = true;
        for (const actionButton of list.querySelectorAll("button")) actionButton.disabled = true;
        status.textContent = "";
        status.hidden = true;
        let succeeded = false;
        try {
            const payload = await withDeadline((signal) => api.postJson(
                url,
                {action: code.toLowerCase()},
                csrfToken,
                {signal},
            ));
            if (!started || generation !== requestGeneration) return;
            succeeded = true;
            const roomUrl = safeNavigationUrl(payload?.room_url);
            if (code === "ACCEPT" && roomUrl) {
                navigate(roomUrl);
                return;
            }
        } catch (error) {
            if (started && generation === requestGeneration) {
                status.textContent = error?.message || "Chưa thể xử lý lời mời";
                status.hidden = false;
            }
        } finally {
            if (generation === requestGeneration) busy = false;
        }
        if (started && generation === requestGeneration && succeeded) {
            await polling.refresh();
        } else if (started && generation === requestGeneration) {
            for (const actionButton of list.querySelectorAll("button")) {
                actionButton.disabled = false;
            }
        }
    }

    function handleTrigger() {
        setOpen(panel.hidden);
    }

    function handleDocumentClick(event) {
        if (!panel.hidden && !root.contains(event.target)) setOpen(false);
    }

    function handleDocumentKeydown(event) {
        if (event.key === "Escape" && !panel.hidden) {
            event.preventDefault();
            setOpen(false, {restoreFocus: true});
        }
    }

    function handleVisibility() {
        polling.reschedule();
    }

    function handleExternalRefresh() {
        void polling.refresh();
    }

    function handlePageHide() {
        stop({keepPageShow: true});
    }

    function handlePageShow(event) {
        if (event.persisted) start();
    }

    function start() {
        if (started) return;
        started = true;
        trigger.addEventListener("click", handleTrigger);
        documentRoot.addEventListener("click", handleDocumentClick);
        documentRoot.addEventListener("keydown", handleDocumentKeydown);
        documentRoot.addEventListener("visibilitychange", handleVisibility);
        windowObject.addEventListener("social:notifications-refresh", handleExternalRefresh);
        windowObject.addEventListener("pagehide", handlePageHide);
        windowObject.addEventListener("pageshow", handlePageShow);
        polling.start();
    }

    function stop({keepPageShow = false} = {}) {
        if (!started) return;
        started = false;
        generation += 1;
        busy = false;
        abortController?.abort();
        polling.stop();
        trigger.removeEventListener("click", handleTrigger);
        documentRoot.removeEventListener("click", handleDocumentClick);
        documentRoot.removeEventListener("keydown", handleDocumentKeydown);
        documentRoot.removeEventListener("visibilitychange", handleVisibility);
        windowObject.removeEventListener("social:notifications-refresh", handleExternalRefresh);
        windowObject.removeEventListener("pagehide", handlePageHide);
        if (!keepPageShow) windowObject.removeEventListener("pageshow", handlePageShow);
    }

    return {start, stop, refresh, setOpen};
}
