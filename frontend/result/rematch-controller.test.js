import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createBattleApi} from "../battle/api.js";
import {createRematchController} from "./rematch-controller.js";
import {initializeResult} from "./result-app.js";

const initial = {
    status: "NONE", terminal: false, is_requester: false, actions: ["request"],
    server_time: "2026-08-30T10:00:00Z", expires_at: null,
    requester_name: null, room_url: null, new_match_status: null, unavailable_reason: "",
};
const pending = {
    ...initial, status: "PENDING", actions: ["accept", "decline"],
    requester_name: "host", expires_at: "2026-08-30T10:02:00Z",
};
const accepted = {
    ...pending, status: "ACCEPTED", terminal: true, actions: [],
    room_url: "/matches/rooms/NEW123/", new_match_status: "WAITING",
};
let controllers;

beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    document.body.innerHTML = `
        <section id="rematch-controls">
            <p data-rematch-notice role="status"></p><p data-rematch-error></p>
            <button type="button" data-rematch-action="request">Tái đấu</button>
            <button type="button" data-rematch-action="accept">Đồng ý</button>
            <button type="button" data-rematch-action="decline">Từ chối</button>
            <button type="button" data-rematch-action="cancel">Hủy lời mời</button>
            <a data-rematch-open></a><button data-rematch-refresh>Cập nhật</button>
        </section>
        <form id="rematch-csrf"><input name="csrfmiddlewaretoken" value="csrf"></form>`;
    controllers = [];
});

afterEach(() => {
    controllers.forEach((c) => c.stop());
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
});

function setup(state = initial, api = {getJson: vi.fn(), postJson: vi.fn()}) {
    const navigate = vi.fn();
    const controller = createRematchController({
        api, stateUrl: "/state", actionUrl: "/action", csrfToken: "csrf", navigate,
    });
    controller.start(state);
    controllers.push(controller);
    return {api, controller, navigate};
}
const button = (action) => document.querySelector(`[data-rematch-action="${action}"]`);
const errorText = () => document.querySelector("[data-rematch-error]").textContent;
const noticeText = () => document.querySelector("[data-rematch-notice]").textContent;

describe("rematch controller", () => {
    it("polls even NONE to receive invitations, then stops on a terminal state", async () => {
        const {api} = setup();
        api.getJson.mockResolvedValueOnce(pending).mockResolvedValue({...pending, status: "DECLINED", terminal: true, actions: []});
        await vi.advanceTimersByTimeAsync(5000);
        expect(button("accept").hidden).toBe(false);
        expect(noticeText()).toContain("host mời bạn");
        await vi.advanceTimersByTimeAsync(5000);
        expect(noticeText()).toContain("từ chối");
        await vi.advanceTimersByTimeAsync(60000);
        expect(api.getJson).toHaveBeenCalledTimes(2);
    });

    it("reschedules to 30 seconds when hidden and supports manual refresh", async () => {
        const {api} = setup();
        api.getJson.mockResolvedValue(initial);
        vi.spyOn(document, "hidden", "get").mockReturnValue(true);
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.advanceTimersByTimeAsync(29000);
        expect(api.getJson).not.toHaveBeenCalled();
        await vi.advanceTimersByTimeAsync(1000);
        expect(api.getJson).toHaveBeenCalledTimes(1);
        document.querySelector("[data-rematch-refresh]").click();
        await vi.advanceTimersByTimeAsync(0);
        expect(api.getJson).toHaveBeenCalledTimes(2);
    });

    it("disables actions immediately, blocks overlap, and navigates when invitation is accepted", async () => {
        let resolve;
        const api = {getJson: vi.fn().mockResolvedValue({...accepted, is_requester: true}), postJson: vi.fn(() => new Promise((r) => {resolve = r;}))};
        const {controller, navigate} = setup(initial, api);
        button("request").click();
        button("request").click();
        await controller.refresh();
        expect(button("request").disabled).toBe(true);
        expect(api.postJson).toHaveBeenCalledTimes(1);
        expect(api.postJson).toHaveBeenCalledWith("/action", {action: "request"}, "csrf", {signal: expect.any(AbortSignal)});
        expect(api.getJson).not.toHaveBeenCalled();
        resolve({...pending, is_requester: true, actions: ["cancel"]});
        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(5000);
        expect(navigate).toHaveBeenCalledTimes(1);
        expect(navigate.mock.calls[0][0]).toContain("/matches/rooms/NEW123/");
    });

    it("accepts through the same CSRF API and does not auto-navigate historical results", async () => {
        const old = setup(accepted);
        expect(old.navigate).not.toHaveBeenCalled();
        expect(document.querySelector("[data-rematch-open]").hidden).toBe(false);
        old.controller.stop();
        const current = setup(pending);
        current.api.postJson.mockResolvedValue(accepted);
        button("accept").click();
        await vi.advanceTimersByTimeAsync(0);
        expect(current.navigate).toHaveBeenCalledTimes(1);
    });

    it("aborts timed-out requests, preserves state and recovers on the next poll", async () => {
        let resolveLate;
        const api = {getJson: vi.fn().mockImplementationOnce(() => new Promise((r) => {resolveLate = r;})).mockResolvedValue(pending)};
        const {controller} = setup(initial, api);
        const request = controller.refresh();
        await vi.advanceTimersByTimeAsync(10000);
        await request;
        expect(api.getJson.mock.calls[0][1].signal.aborted).toBe(true);
        expect(errorText()).toContain("10 giây");
        expect(noticeText()).toBe("Mời chơi lại");
        await vi.advanceTimersByTimeAsync(5000);
        expect(button("accept").hidden).toBe(false);
        resolveLate(accepted);
        await vi.advanceTimersByTimeAsync(0);
        expect(noticeText()).toContain("mời bạn");
    });

    it.each(["network", "non-json", "http"])("keeps state on %s errors and safely recovers", async (failure) => {
        const fetchImpl = vi.fn();
        if (failure === "network") fetchImpl.mockRejectedValueOnce(new Error("offline"));
        if (failure === "non-json") fetchImpl.mockResolvedValueOnce({ok: true, status: 200, json: async () => {throw new SyntaxError("html");}});
        if (failure === "http") fetchImpl.mockResolvedValueOnce({ok: false, status: 409, json: async () => ({code: "REMATCH_CLOSED", message: "Lời mời đã đóng."})});
        fetchImpl.mockResolvedValue({ok: true, status: 200, json: async () => pending});
        const {controller} = setup(initial, createBattleApi({fetchImpl}));
        await controller.refresh();
        expect(errorText()).not.toBe("");
        expect(button("request").disabled).toBe(false);
        await controller.refresh();
        expect(errorText()).toBe("");
        expect(button("accept").hidden).toBe(false);
    });

    it("restores controls after a failed POST and does not trust arbitrary URLs or markup", async () => {
        const {api} = setup({...pending, requester_name: "<img src=x onerror=alert(1)>"});
        api.postJson.mockRejectedValue(new Error("Không thể chấp nhận."));
        button("accept").click();
        await vi.advanceTimersByTimeAsync(0);
        expect(button("accept").disabled).toBe(false);
        expect(document.querySelector("img")).toBeNull();
        api.getJson.mockResolvedValue({...accepted, room_url: "javascript:alert(1)"});
        document.querySelector("[data-rematch-refresh]").click();
        await vi.advanceTimersByTimeAsync(0);
        expect(document.querySelector("[data-rematch-open]").hasAttribute("href")).toBe(false);
    });

    it("does not send a hidden/unavailable action and stops on pagehide", async () => {
        const {api} = setup({...initial, actions: [], unavailable_reason: "Người chơi đang bận."});
        button("request").click();
        expect(api.postJson).not.toHaveBeenCalled();
        window.dispatchEvent(new Event("pagehide"));
        await vi.advanceTimersByTimeAsync(60000);
        expect(api.getJson).not.toHaveBeenCalled();
    });

    it("restores keyboard focus after polling and refreshes when returning through bfcache", async () => {
        const {api, controller} = setup();
        api.getJson.mockResolvedValue(initial);
        button("request").focus();
        await controller.refresh();
        expect(document.activeElement).toBe(button("request"));
        window.dispatchEvent(new Event("pagehide"));
        window.dispatchEvent(new PageTransitionEvent("pageshow", {persisted: true}));
        await vi.advanceTimersByTimeAsync(0);
        expect(api.getJson).toHaveBeenCalledTimes(2);
    });

    it("keeps the new request abortable when an older generation finishes cleanup", async () => {
        const api = {getJson: vi.fn(() => new Promise(() => {}))};
        const {controller} = setup(initial, api);
        const oldRequest = controller.refresh();
        controller.stop();
        controller.start(initial);
        const newRequest = controller.refresh();
        await oldRequest;
        controller.stop();
        expect(api.getJson.mock.calls[1][1].signal.aborted).toBe(true);
        await newRequest;
        expect(errorText()).toBe("");
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
        config.textContent = JSON.stringify({stateUrl: "/state", actionUrl: "/action", initialState: initial});
        document.body.append(config);
        controllers.push(...initializeResult());
        expect(controllers).toHaveLength(1);
        expect(button("request").hidden).toBe(false);
    });
});
