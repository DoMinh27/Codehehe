import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createReviewController} from "./review-controller.js";


afterEach(() => {
    vi.useRealTimers();
});

beforeEach(() => {
    document.body.innerHTML = '<div id="ai-review-list"></div>';
});


describe("AI review controller", () => {
    it("polls pending state and stops after completion", async () => {
        vi.useFakeTimers();
        const completed = {terminal: true, players: []};
        const api = {getJson: vi.fn().mockResolvedValue(completed)};
        const renderer = {
            render: vi.fn(),
            showTemporaryError: vi.fn(),
        };
        const controller = createReviewController({
            api,
            stateUrl: "/reviews",
            renderer,
            documentRoot: document,
            windowObject: window,
        });

        controller.start({terminal: false, players: []});
        await vi.advanceTimersByTimeAsync(5000);
        await vi.advanceTimersByTimeAsync(30000);

        expect(api.getJson).toHaveBeenCalledTimes(1);
        expect(renderer.render).toHaveBeenLastCalledWith(completed);
        controller.stop();
    });

    it("keeps polling after a temporary API error", async () => {
        vi.useFakeTimers();
        const api = {
            getJson: vi.fn()
                .mockRejectedValueOnce(new Error("offline"))
                .mockResolvedValueOnce({terminal: true, players: []}),
        };
        const renderer = {
            render: vi.fn(),
            showTemporaryError: vi.fn(),
        };
        const controller = createReviewController({
            api,
            stateUrl: "/reviews",
            renderer,
            documentRoot: document,
            windowObject: window,
        });

        controller.start({terminal: false, players: []});
        await vi.advanceTimersByTimeAsync(5000);
        await vi.advanceTimersByTimeAsync(5000);

        expect(api.getJson).toHaveBeenCalledTimes(2);
        expect(renderer.showTemporaryError).toHaveBeenCalledWith("offline");
        controller.stop();
    });

    it("disables a request immediately and prevents a double click", async () => {
        let resolveRequest;
        const api = {
            getJson: vi.fn(),
            post: vi.fn(() => new Promise((resolve) => {
                resolveRequest = resolve;
            })),
        };
        const renderer = {render: vi.fn(), showTemporaryError: vi.fn()};
        const controller = createReviewController({
            api,
            stateUrl: "/reviews",
            csrfToken: "token",
            renderer,
            documentRoot: document,
            windowObject: window,
        });
        controller.start({terminal: true, players: []});
        const button = document.createElement("button");
        button.dataset.aiReviewRequest = "/request";
        document.getElementById("ai-review-list").appendChild(button);

        button.click();
        button.click();

        expect(button.disabled).toBe(true);
        expect(api.post).toHaveBeenCalledTimes(1);
        expect(api.post).toHaveBeenCalledWith("/request", "token");
        resolveRequest({terminal: true, players: []});
        await Promise.resolve();
        controller.stop();
    });

    it("restarts polling after requesting from a terminal state", async () => {
        vi.useFakeTimers();
        const api = {
            post: vi.fn().mockResolvedValue({terminal: false, players: []}),
            getJson: vi.fn().mockResolvedValue({terminal: true, players: []}),
        };
        const renderer = {render: vi.fn(), showTemporaryError: vi.fn()};
        const controller = createReviewController({
            api,
            stateUrl: "/reviews",
            csrfToken: "token",
            renderer,
            documentRoot: document,
            windowObject: window,
        });
        controller.start({terminal: true, players: []});
        const button = document.createElement("button");
        button.dataset.aiReviewRequest = "/request";
        document.getElementById("ai-review-list").appendChild(button);

        button.click();
        await Promise.resolve();
        await vi.advanceTimersByTimeAsync(5000);

        expect(api.getJson).toHaveBeenCalledTimes(1);
        controller.stop();
    });

    it("does not send a request from a disabled button", () => {
        const api = {getJson: vi.fn(), post: vi.fn()};
        const renderer = {render: vi.fn(), showTemporaryError: vi.fn()};
        const controller = createReviewController({
            api,
            stateUrl: "/reviews",
            csrfToken: "token",
            renderer,
            documentRoot: document,
            windowObject: window,
        });
        controller.start({terminal: true, players: []});
        const button = document.createElement("button");
        button.disabled = true;
        button.dataset.aiReviewRequest = "/request";
        document.getElementById("ai-review-list").appendChild(button);

        button.click();

        expect(api.post).not.toHaveBeenCalled();
        controller.stop();
    });
});
