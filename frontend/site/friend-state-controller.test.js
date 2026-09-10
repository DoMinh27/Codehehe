// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createFriendStateController} from "./friend-state-controller.js";


let controller;


beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    document.body.innerHTML = "";
});


afterEach(() => {
    controller?.stop();
    controller = null;
    vi.restoreAllMocks();
    vi.useRealTimers();
});


describe("friend state controller", () => {
    it("updates existing rows without rebuilding their actions", async () => {
        document.body.innerHTML = `
            <section data-friend-presence-list data-mode="existing" data-state-url="/friends/state/">
                <div data-friend-id="2">
                    <span data-presence-label class="presence-label presence-label--inactive"><span></span>Không hoạt động</span>
                    <button id="keep-focus">Tùy chọn</button>
                </div>
            </section>`;
        const button = document.querySelector("#keep-focus");
        const api = {getJson: vi.fn().mockResolvedValue({
            server_time: "2026-09-09T10:00:00Z",
            friends: [{id: 2, username: "bob", initial: "B", status: "READY", status_label: "Sẵn sàng"}],
        })};
        controller = createFriendStateController({api, documentRoot: document, windowObject: window});
        controller.start();
        await vi.advanceTimersByTimeAsync(0);

        expect(document.body.textContent).toContain("Sẵn sàng");
        expect(document.querySelector("#keep-focus")).toBe(button);
    });

    it("renders at most five ready friends in the lobby", async () => {
        document.body.innerHTML = `
            <section data-friend-presence-list data-mode="ready" data-state-url="/friends/state/">
                <ul data-friend-list hidden></ul><p data-friend-empty>Empty</p>
            </section>`;
        const friends = Array.from({length: 7}, (_, index) => ({
            id: index + 1,
            username: `user-${index}`,
            initial: "U",
            status: index === 6 ? "INACTIVE" : "READY",
            status_label: index === 6 ? "Không hoạt động" : "Sẵn sàng",
        }));
        const api = {getJson: vi.fn().mockResolvedValue({server_time: "now", friends})};
        controller = createFriendStateController({api, documentRoot: document, windowObject: window});
        controller.start();
        await vi.advanceTimersByTimeAsync(0);

        expect(document.querySelectorAll("[data-friend-id]")).toHaveLength(5);
        expect(document.querySelector("[data-friend-list]").hidden).toBe(false);
        expect(document.querySelector("[data-friend-empty]").hidden).toBe(true);
    });

    it("keeps the last state when a later payload is invalid", async () => {
        document.body.innerHTML = `
            <section data-friend-presence-list data-mode="ready" data-state-url="/friends/state/">
                <ul data-friend-list></ul><p data-friend-empty></p>
            </section>`;
        const api = {getJson: vi.fn()
            .mockResolvedValueOnce({friends: [{id: 2, username: "bob", initial: "B", status: "READY", status_label: "Sẵn sàng"}]})
            .mockResolvedValueOnce({friends: [{id: 2, status: "UNKNOWN"}]})};
        controller = createFriendStateController({
            api,
            documentRoot: document,
            windowObject: window,
            visibleDelay: 100,
        });
        controller.start();
        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(100);

        expect(document.body.textContent).toContain("bob");
    });
});
