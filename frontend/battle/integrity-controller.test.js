import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createIntegrityController} from "./integrity-controller.js";


function uuidFactory() {
    let value = 0;
    return () => `00000000-0000-4000-8000-${String(++value).padStart(12, "0")}`;
}


describe("Fair Play integrity controller", () => {
    let api;
    let controller;
    let notice;

    beforeEach(() => {
        vi.useFakeTimers();
        window.sessionStorage.clear();
        Object.defineProperty(document, "hidden", {
            configurable: true,
            value: false,
        });
        api = {
            postJson: vi.fn().mockResolvedValue({
                accepted_event_ids: [],
                notice: null,
            }),
        };
        notice = vi.fn();
        controller = createIntegrityController({
            documentRoot: document,
            windowObject: window,
            api,
            config: {
                integrity: {
                    url: "/matches/1/integrity/events/",
                    heartbeatMs: 10000,
                    requestTimeoutMs: 5000,
                    maxQueueSize: 50,
                },
            },
            csrfToken: "csrf",
            identity: {userId: 1, matchId: 1},
            randomUUID: uuidFactory(),
            onNotice: notice,
        });
    });

    afterEach(() => {
        controller.stop();
        vi.useRealTimers();
        window.sessionStorage.clear();
    });

    async function startAndAcceptInitial() {
        api.postJson.mockImplementationOnce(async (_url, body) => ({
            accepted_event_ids: body.events.map((event) => event.event_id),
            notice: null,
        }));
        controller.start();
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(1));
        api.postJson.mockClear();
    }

    it("sends page return at start and heartbeat every ten seconds", async () => {
        await startAndAcceptInitial();

        api.postJson.mockImplementationOnce(async (_url, body) => ({
            accepted_event_ids: body.events.map((event) => event.event_id),
            notice: null,
        }));
        await vi.advanceTimersByTimeAsync(10000);

        expect(api.postJson).toHaveBeenCalledTimes(1);
        expect(api.postJson.mock.calls[0][1].events[0].kind).toBe("HEARTBEAT");
    });

    it("reports hidden, visible and page lifecycle without beforeunload", async () => {
        await startAndAcceptInitial();
        api.postJson.mockImplementation(async (_url, body) => ({
            accepted_event_ids: body.events.map((event) => event.event_id),
            notice: body.events.some((event) => event.kind === "VISIBLE")
                ? {code: "FOCUS_VIOLATION_RECORDED", message: "Đã ghi nhận"}
                : null,
        }));

        Object.defineProperty(document, "hidden", {configurable: true, value: true});
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(1));
        Object.defineProperty(document, "hidden", {configurable: true, value: false});
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(2));
        window.dispatchEvent(new Event("pagehide"));
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(3));

        expect(api.postJson.mock.calls[0][1].events[0].kind).toBe("HIDDEN");
        expect(api.postJson.mock.calls[1][1].events[0].kind).toBe("VISIBLE");
        expect(api.postJson.mock.calls[2][1].events[0].kind).toBe("PAGE_LEAVE");
        expect(api.postJson.mock.calls[2][3].keepalive).toBe(true);
        expect(notice).toHaveBeenCalledWith({
            code: "FOCUS_VIOLATION_RECORDED",
            message: "Đã ghi nhận",
        });
    });

    it("records only paste length and retries a failed queued event", async () => {
        await startAndAcceptInitial();
        api.postJson.mockRejectedValueOnce(new Error("offline"));
        controller.recordPaste(123);
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(1));
        const firstBody = api.postJson.mock.calls[0][1];
        expect(firstBody.events[0]).toMatchObject({
            kind: "PASTE",
            character_count: 123,
        });
        expect(JSON.stringify(firstBody)).not.toContain("source");

        api.postJson.mockImplementationOnce(async (_url, body) => ({
            accepted_event_ids: body.events.map((event) => event.event_id),
            notice: null,
        }));
        await controller.flush();
        expect(api.postJson).toHaveBeenCalledTimes(2);
        expect(api.postJson.mock.calls[1][1].events[0].event_id).toBe(
            firstBody.events[0].event_id,
        );
    });

    it("does not overlap requests and removes listeners when stopped", async () => {
        await startAndAcceptInitial();
        let resolveRequest;
        api.postJson.mockReturnValueOnce(
            new Promise((resolve) => {
                resolveRequest = resolve;
            }),
        );
        controller.recordPaste(10);
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(1));
        await vi.advanceTimersByTimeAsync(20000);
        expect(api.postJson).toHaveBeenCalledTimes(1);
        resolveRequest({accepted_event_ids: [], notice: null});
        await Promise.resolve();

        controller.stop();
        document.dispatchEvent(new Event("visibilitychange"));
        window.dispatchEvent(new Event("pageshow"));
        await vi.advanceTimersByTimeAsync(20000);
        expect(api.postJson).toHaveBeenCalledTimes(1);
    });

    it("aborts a stalled request and retries it later", async () => {
        await startAndAcceptInitial();
        api.postJson.mockImplementationOnce((_url, _body, _csrf, options) => (
            new Promise((_resolve, reject) => {
                options.signal.addEventListener("abort", () => reject(new Error("timeout")));
            })
        ));
        controller.recordPaste(8);
        await vi.waitFor(() => expect(api.postJson).toHaveBeenCalledTimes(1));

        await vi.advanceTimersByTimeAsync(5000);
        api.postJson.mockImplementationOnce(async (_url, body) => ({
            accepted_event_ids: body.events.map((event) => event.event_id),
            notice: null,
        }));
        await controller.flush();

        expect(api.postJson).toHaveBeenCalledTimes(2);
        expect(api.postJson.mock.calls[1][1].events[0].kind).toBe("PASTE");
    });

    it("keeps the persistent queue bounded", async () => {
        await startAndAcceptInitial();
        api.postJson.mockReturnValue(new Promise(() => {}));
        for (let index = 0; index < 75; index += 1) {
            controller.recordPaste(index);
        }

        const queueKey = Object.keys(window.sessionStorage)
            .find((key) => key.endsWith("integrity-queue"));
        const stored = JSON.parse(window.sessionStorage.getItem(queueKey));

        expect(stored).toHaveLength(50);
        expect(stored[0].character_count).toBe(25);
    });
});
