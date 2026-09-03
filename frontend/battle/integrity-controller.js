const CLIENT_SESSION_SUFFIX = "integrity-client";
const QUEUE_SUFFIX = "integrity-queue";


function storageKey(identity, suffix) {
    return `codehehe:${identity.userId}:${identity.matchId}:${suffix}`;
}


function readQueue(storage, key) {
    try {
        const value = JSON.parse(storage.getItem(key) || "[]");
        return Array.isArray(value) ? value : [];
    } catch {
        return [];
    }
}


function writeQueue(storage, key, queue) {
    try {
        storage.setItem(key, JSON.stringify(queue));
    } catch {
        // Fair Play telemetry must never break the Battle UI.
    }
}


function getClientSessionId(storage, key, randomUUID) {
    try {
        const existing = storage.getItem(key);
        if (existing) return existing;
        const created = randomUUID();
        storage.setItem(key, created);
        return created;
    } catch {
        return randomUUID();
    }
}


export function createIntegrityController({
    documentRoot = document,
    windowObject = window,
    api,
    config,
    csrfToken,
    identity,
    randomUUID,
    onNotice = () => {},
}) {
    const options = config.integrity;
    const storage = windowObject.sessionStorage;
    const queueKey = storageKey(identity, QUEUE_SUFFIX);
    const clientKey = storageKey(identity, CLIENT_SESSION_SUFFIX);
    const clientSessionId = getClientSessionId(storage, clientKey, randomUUID);
    const maxQueueSize = Number(options.maxQueueSize) || 50;
    let queue = readQueue(storage, queueKey).slice(-maxQueueSize);
    let inFlight = false;
    let stopped = true;
    let heartbeatHandle = null;

    function persist() {
        writeQueue(storage, queueKey, queue);
    }

    function enqueue(kind, extra = {}) {
        if (kind === "HEARTBEAT" && queue.some((item) => item.kind === kind)) {
            return;
        }
        queue.push({event_id: randomUUID(), kind, ...extra});
        queue = queue.slice(-maxQueueSize);
        persist();
    }

    async function flush({keepalive = false} = {}) {
        if (inFlight || !queue.length) return;
        inFlight = true;
        const batch = queue.slice(0, 20);
        const controller = new AbortController();
        const timeoutHandle = keepalive
            ? null
            : windowObject.setTimeout(
                () => controller.abort(),
                Number(options.requestTimeoutMs) || 5000,
            );
        try {
            const payload = await api.postJson(
                options.url,
                {client_session_id: clientSessionId, events: batch},
                csrfToken,
                {signal: controller.signal, keepalive},
            );
            const accepted = new Set(payload.accepted_event_ids || []);
            queue = queue.filter((item) => !accepted.has(item.event_id));
            persist();
            if (payload.notice?.message) onNotice(payload.notice);
        } catch {
            // Keep the bounded queue for the next heartbeat/reconnect attempt.
        } finally {
            if (timeoutHandle !== null) windowObject.clearTimeout(timeoutHandle);
            inFlight = false;
        }
    }

    function heartbeat() {
        if (stopped) return;
        enqueue("HEARTBEAT");
        void flush();
    }

    function handleVisibilityChange() {
        enqueue(documentRoot.hidden ? "HIDDEN" : "VISIBLE");
        void flush();
    }

    function handlePageHide() {
        enqueue("PAGE_LEAVE");
        void flush({keepalive: true});
    }

    function handlePageShow() {
        enqueue("PAGE_RETURN");
        void flush();
    }

    return {
        start() {
            if (!stopped) return;
            stopped = false;
            documentRoot.addEventListener("visibilitychange", handleVisibilityChange);
            windowObject.addEventListener("pagehide", handlePageHide);
            windowObject.addEventListener("pageshow", handlePageShow);
            enqueue("PAGE_RETURN");
            void flush();
            heartbeatHandle = windowObject.setInterval(
                heartbeat,
                Number(options.heartbeatMs) || 10000,
            );
        },
        recordPaste(characterCount) {
            if (stopped) return;
            enqueue("PASTE", {
                character_count: Math.max(0, Math.floor(Number(characterCount) || 0)),
            });
            void flush();
        },
        stop() {
            if (stopped) return;
            stopped = true;
            windowObject.clearInterval(heartbeatHandle);
            documentRoot.removeEventListener(
                "visibilitychange",
                handleVisibilityChange,
            );
            windowObject.removeEventListener("pagehide", handlePageHide);
            windowObject.removeEventListener("pageshow", handlePageShow);
        },
        flush,
    };
}
