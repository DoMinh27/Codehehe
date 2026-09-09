import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createRematchController} from "./rematch-controller.js";
import {initializeResult} from "./result-app.js";


const initial = {
    status: "NONE",
    terminal: false,
    is_requester: false,
    actions: ["request"],
    server_time: "2026-08-30T10:00:00Z",
    expires_at: null,
    requester_name: null,
    room_url: null,
    new_match_status: null,
    unavailable_reason: "",
};
const outgoing = {
    ...initial,
    status: "PENDING",
    is_requester: true,
    actions: ["cancel"],
    expires_at: "2026-08-30T10:02:00Z",
};
let controllers;


beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = `
        <div id="rematch-controls">
            <button type="button" data-rematch-request>Mời tái đấu</button>
            <span data-rematch-status role="status"></span>
        </div>
        <form id="rematch-csrf"><input name="csrfmiddlewaretoken" value="csrf"></form>`;
    controllers = [];
});

afterEach(() => {
    controllers.forEach((controller) => controller.stop());
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
});


function setup(state = initial, api = {postJson: vi.fn()}) {
    const controller = createRematchController({
        api,
        actionUrl: "/matches/1/rematch/",
        csrfToken: "csrf",
        documentRoot: document,
        windowObject: window,
    });
    controller.start(state);
    controllers.push(controller);
    return {api, controller};
}


describe("compact rematch controller", () => {
    it("sends one request, updates the button and refreshes notifications", async () => {
        const api = {postJson: vi.fn().mockResolvedValue(outgoing)};
        const refreshListener = vi.fn();
        window.addEventListener("social:notifications-refresh", refreshListener, {once: true});
        setup(initial, api);

        const button = document.querySelector("[data-rematch-request]");
        button.click();
        button.click();
        await vi.advanceTimersByTimeAsync(0);

        expect(api.postJson).toHaveBeenCalledTimes(1);
        expect(api.postJson).toHaveBeenCalledWith(
            "/matches/1/rematch/",
            {action: "request"},
            "csrf",
            {signal: expect.any(AbortSignal)},
        );
        expect(button.disabled).toBe(true);
        expect(button.textContent).toBe("Đã gửi lời mời");
        expect(document.querySelector("[data-rematch-status]").textContent)
            .toContain("Thông báo");
        expect(refreshListener).toHaveBeenCalledOnce();
    });

    it("does not send unavailable, incoming or terminal actions", () => {
        const states = [
            {...initial, actions: [], unavailable_reason: "Người chơi đang bận."},
            {...outgoing, is_requester: false, actions: ["accept", "decline"]},
            {...initial, status: "EXPIRED", terminal: true, actions: []},
        ];
        for (const state of states) {
            const {api, controller} = setup(state);
            document.querySelector("[data-rematch-request]").click();
            expect(api.postJson).not.toHaveBeenCalled();
            controller.stop();
        }
    });

    it("restores the compact control after a failed request", async () => {
        const api = {postJson: vi.fn().mockRejectedValue(new Error("Máy chủ đang bận"))};
        setup(initial, api);

        document.querySelector("[data-rematch-request]").click();
        await vi.advanceTimersByTimeAsync(0);

        expect(document.querySelector("[data-rematch-request]").disabled).toBe(false);
        expect(document.querySelector("[data-rematch-status]").textContent)
            .toBe("Máy chủ đang bận");
    });

    it("aborts a request after five seconds and can be stopped safely", async () => {
        const api = {postJson: vi.fn(() => new Promise(() => {}))};
        const {controller} = setup(initial, api);
        document.querySelector("[data-rematch-request]").click();

        await vi.advanceTimersByTimeAsync(5000);
        expect(api.postJson.mock.calls[0][3].signal.aborted).toBe(true);
        controller.stop();
    });
});


describe("Result independent initialization", () => {
    it.each([false, true])("rematch works with absent/broken AI config: %s", (brokenAI) => {
        vi.stubGlobal("fetch", vi.fn());
        if (brokenAI) {
            const ai = document.createElement("script");
            ai.type = "application/json";
            ai.id = "ai-review-config";
            ai.textContent = "broken";
            document.body.append(ai);
            const notice = document.createElement("p");
            notice.id = "ai-review-notice";
            document.body.append(notice);
        }
        const config = document.createElement("script");
        config.type = "application/json";
        config.id = "rematch-config";
        config.textContent = JSON.stringify({
            actionUrl: "/matches/1/rematch/",
            initialState: initial,
        });
        document.body.append(config);

        controllers.push(...initializeResult());

        expect(controllers).toHaveLength(1);
        expect(document.querySelector("[data-rematch-request]").hidden).toBe(false);
    });
});
