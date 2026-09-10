import {createPolling} from "../battle/polling.js";


const STATUSES = new Set(["READY", "WAITING", "PLAYING", "INACTIVE"]);
const STATUS_CLASSES = [
    "presence-label--ready",
    "presence-label--waiting",
    "presence-label--playing",
    "presence-label--inactive",
];


function validateState(payload) {
    if (!payload || !Array.isArray(payload.friends)) {
        throw new Error("Dữ liệu trạng thái không hợp lệ");
    }
    for (const friend of payload.friends) {
        if (!friend || !Number.isInteger(friend.id)
            || typeof friend.username !== "string" || typeof friend.initial !== "string"
            || !STATUSES.has(friend.status) || typeof friend.status_label !== "string") {
            throw new Error("Dữ liệu trạng thái không hợp lệ");
        }
    }
    return payload;
}


export function createFriendStateController({
    api,
    documentRoot = document,
    windowObject = window,
    visibleDelay = 30000,
    hiddenDelay = 60000,
}) {
    const roots = [...documentRoot.querySelectorAll("[data-friend-presence-list]")];
    if (!roots.length) return null;
    let started = false;
    let abortController = null;

    function setStatus(label, friend) {
        label.classList.remove(...STATUS_CLASSES);
        label.classList.add(`presence-label--${friend.status.toLowerCase()}`);
        const dot = label.querySelector("span") || documentRoot.createElement("span");
        dot.setAttribute("aria-hidden", "true");
        label.replaceChildren(dot, friend.status_label);
    }

    function makeReadyRow(friend) {
        const row = documentRoot.createElement("li");
        row.className = "social-row";
        row.dataset.friendId = String(friend.id);
        const avatar = documentRoot.createElement("span");
        avatar.className = "avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = friend.initial;
        const main = documentRoot.createElement("div");
        main.className = "social-row__main";
        const username = documentRoot.createElement("strong");
        username.textContent = friend.username;
        const label = documentRoot.createElement("span");
        label.className = "presence-label";
        label.dataset.presenceLabel = "";
        setStatus(label, friend);
        main.append(username, label);
        row.append(avatar, main);
        return row;
    }

    function render(payload) {
        const friendById = new Map(payload.friends.map((friend) => [String(friend.id), friend]));
        for (const root of roots) {
            if (root.dataset.mode === "ready") {
                const ready = payload.friends.filter((friend) => friend.status === "READY").slice(0, 5);
                const list = root.querySelector("[data-friend-list]");
                list.replaceChildren(...ready.map(makeReadyRow));
                list.hidden = ready.length === 0;
                const empty = root.querySelector("[data-friend-empty]");
                if (empty) empty.hidden = ready.length !== 0;
                continue;
            }
            for (const row of root.querySelectorAll("[data-friend-id]")) {
                const friend = friendById.get(row.dataset.friendId);
                const label = row.querySelector("[data-presence-label]");
                if (friend && label) setStatus(label, friend);
            }
        }
    }

    async function refresh() {
        if (!started) return;
        const controller = new windowObject.AbortController();
        abortController = controller;
        const timeout = windowObject.setTimeout(() => controller.abort(), 5000);
        try {
            const payload = await api.getJson(roots[0].dataset.stateUrl, {
                signal: controller.signal,
            });
            if (started) render(validateState(payload));
        } catch {
            // Keep the last known state and retry on the next polling cycle.
        } finally {
            windowObject.clearTimeout(timeout);
            if (abortController === controller) abortController = null;
        }
    }

    const polling = createPolling({
        refresh,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
        visibleDelay,
        hiddenDelay,
    });

    function handleVisibility() {
        polling.reschedule();
    }

    function start() {
        if (started) return;
        started = true;
        documentRoot.addEventListener("visibilitychange", handleVisibility);
        polling.start();
    }

    function stop() {
        if (!started) return;
        started = false;
        abortController?.abort();
        polling.stop();
        documentRoot.removeEventListener("visibilitychange", handleVisibility);
    }

    return {start, stop, refresh};
}
