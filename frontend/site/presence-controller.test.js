// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createPresenceController} from "./presence-controller.js";


let hiddenSpy;
let controller;


beforeEach(() => {
    vi.useFakeTimers();
    hiddenSpy = vi.spyOn(document, "hidden", "get").mockReturnValue(false);
});


afterEach(() => {
    controller?.stop();
    controller = null;
    vi.restoreAllMocks();
    vi.useRealTimers();
});


describe("presence controller", () => {
    it("sends immediately and then every visible interval", async () => {
        const api = {postJson: vi.fn().mockResolvedValue({ok: true})};
        controller = createPresenceController({
            api,
            url: "/presence/heartbeat/",
            csrfToken: "csrf",
            documentRoot: document,
            windowObject: window,
            intervalMs: 30000,
        });

        controller.start();
        await vi.advanceTimersByTimeAsync(0);
        expect(api.postJson).toHaveBeenCalledOnce();
        await vi.advanceTimersByTimeAsync(30000);
        expect(api.postJson).toHaveBeenCalledTimes(2);
    });

    it("pauses while hidden and resumes immediately when visible", async () => {
        const api = {postJson: vi.fn().mockResolvedValue({ok: true})};
        controller = createPresenceController({
            api,
            url: "/presence/heartbeat/",
            csrfToken: "csrf",
            documentRoot: document,
            windowObject: window,
        });
        controller.start();
        await vi.advanceTimersByTimeAsync(0);

        hiddenSpy.mockReturnValue(true);
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.advanceTimersByTimeAsync(60000);
        expect(api.postJson).toHaveBeenCalledOnce();

        hiddenSpy.mockReturnValue(false);
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.advanceTimersByTimeAsync(0);
        expect(api.postJson).toHaveBeenCalledTimes(2);
    });

    it("does not overlap slow heartbeat requests", async () => {
        let resolveRequest;
        const api = {
            postJson: vi.fn(() => new Promise((resolve) => {
                resolveRequest = resolve;
            })),
        };
        controller = createPresenceController({
            api,
            url: "/presence/heartbeat/",
            csrfToken: "csrf",
            documentRoot: document,
            windowObject: window,
            intervalMs: 30000,
        });
        controller.start();
        await vi.advanceTimersByTimeAsync(30000);
        expect(api.postJson).toHaveBeenCalledOnce();

        resolveRequest({ok: true});
        await vi.advanceTimersByTimeAsync(30000);
        expect(api.postJson).toHaveBeenCalledTimes(2);
    });
});
