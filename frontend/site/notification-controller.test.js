import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createNotificationController} from "./notification-controller.js";


const incoming = {
    key: "REMATCH:1",
    kind: "REMATCH",
    direction: "INCOMING",
    actor: {username: "u1", initial: "U"},
    created_at: "2026-09-09T10:00:00Z",
    expires_at: "2026-09-09T10:02:00Z",
    context: {match_code: "ABC123", score: "2 — 1"},
    context_url: "/matches/1/result/",
    actions: [
        {code: "ACCEPT", url: "/matches/1/rematch/"},
        {code: "DECLINE", url: "/matches/1/rematch/"},
    ],
    unavailable_reason: "",
};
const outgoing = {
    ...incoming,
    key: "REMATCH:2",
    direction: "OUTGOING",
    actor: {username: "u2", initial: "U"},
    context_url: "/matches/2/result/",
    actions: [{code: "CANCEL", url: "/matches/2/rematch/"}],
};
const state = {
    version: 1,
    server_time: "2026-09-09T10:01:00Z",
    incoming_count: 1,
    items: [incoming, outgoing],
};
const friendRequest = {
    key: "FRIEND_REQUEST:1",
    kind: "FRIEND_REQUEST",
    direction: "INCOMING",
    actor: {username: "new-friend", initial: "N"},
    created_at: "2026-09-09T10:00:00Z",
    expires_at: "2026-10-09T10:00:00Z",
    context: {},
    context_url: "/friends/?tab=requests",
    actions: [
        {code: "ACCEPT", url: "/friends/requests/1/action/"},
        {code: "DECLINE", url: "/friends/requests/1/action/"},
    ],
};
const matchInvite = {
    key: "MATCH_INVITE:1",
    kind: "MATCH_INVITE",
    direction: "INCOMING",
    actor: {username: "challenger", initial: "C"},
    created_at: "2026-09-09T10:00:00Z",
    expires_at: "2026-09-09T10:02:00Z",
    context: {mode: "Classic 1v1"},
    context_url: "/friends/",
    actions: [
        {code: "ACCEPT", url: "/match-invitations/1/action/"},
        {code: "DECLINE", url: "/match-invitations/1/action/"},
    ],
    unavailable_reason: "",
};
let controllers;
let hiddenSpy;


beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    hiddenSpy = vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    document.body.innerHTML = [
        '<div data-notification-center>',
        '<button data-notification-trigger aria-expanded="false" aria-controls="notification-panel">Bell</button>',
        '<span data-notification-badge hidden>0</span>',
        '<section id="notification-panel" data-notification-panel hidden>',
        '<span data-notification-status hidden></span>',
        '<div data-notification-list></div>',
        '<p data-notification-empty>Empty</p>',
        '</section></div>',
        '<section data-notification-toasts></section>',
    ].join("");
    controllers = [];
});


afterEach(() => {
    controllers.forEach((controller) => controller.stop());
    vi.restoreAllMocks();
    vi.useRealTimers();
});


function setup(api = {getJson: vi.fn().mockResolvedValue(state), postJson: vi.fn()}) {
    const navigate = vi.fn();
    const controller = createNotificationController({
        api,
        stateUrl: "/notifications/state/",
        csrfToken: "csrf",
        documentRoot: document,
        windowObject: window,
        navigate,
    });
    controller.start();
    controllers.push(controller);
    return {api, controller, navigate};
}


describe("notification controller", () => {
    it("renders and accepts a direct match invitation", async () => {
        const inviteState = {...state, items: [matchInvite]};
        const api = {
            getJson: vi.fn().mockResolvedValue(inviteState),
            postJson: vi.fn().mockResolvedValue({room_url: "/matches/rooms/ABC123/"}),
        };
        const {navigate} = setup(api);
        await vi.advanceTimersByTimeAsync(0);

        expect(document.body.textContent).toContain("challenger mời bạn thi đấu");
        expect(document.body.textContent).toContain("Classic 1v1");
        const accept = [...document.querySelectorAll("[data-notification-action]")]
            .find((button) => button.dataset.notificationAction === "ACCEPT");
        accept.click();
        await vi.advanceTimersByTimeAsync(0);

        expect(api.postJson).toHaveBeenCalledWith(
            "/match-invitations/1/action/",
            {action: "accept"},
            "csrf",
            expect.any(Object),
        );
        expect(navigate).toHaveBeenCalledWith("http://localhost:3000/matches/rooms/ABC123/");
    });

    it("renders a friend request without requiring match context", async () => {
        const friendState = {...state, items: [friendRequest]};
        setup({getJson: vi.fn().mockResolvedValue(friendState), postJson: vi.fn()});
        await vi.advanceTimersByTimeAsync(0);

        expect(document.body.textContent).toContain("new-friend muốn kết bạn");
        expect(document.body.textContent).toContain("Xem bạn bè");
        expect(document.body.textContent).not.toContain("Trận undefined");
    });

    it("renders incoming and outgoing while badge counts only incoming", async () => {
        setup();
        await vi.advanceTimersByTimeAsync(0);

        const badge = document.querySelector("[data-notification-badge]");
        expect(badge.hidden).toBe(false);
        expect(badge.textContent).toBe("1");
        expect(document.querySelectorAll("[data-notification-key]")).toHaveLength(2);
        expect(document.body.textContent).toContain("u1 mời bạn tái đấu");
        expect(document.body.textContent).toContain("Đang chờ u2 phản hồi");
        expect(document.querySelectorAll(".notification-toast")).toHaveLength(1);
    });

    it("shows each new incoming toast once in the browser session", async () => {
        const first = setup();
        await vi.advanceTimersByTimeAsync(0);
        expect(document.querySelectorAll(".notification-toast")).toHaveLength(1);
        first.controller.stop();
        document.querySelector("[data-notification-toasts]").replaceChildren();

        setup();
        await vi.advanceTimersByTimeAsync(0);

        expect(document.querySelectorAll(".notification-toast")).toHaveLength(0);
    });

    it("stacks consecutive incoming notifications from top to bottom", async () => {
        const secondInvite = {
            ...matchInvite,
            key: "MATCH_INVITE:2",
            actor: {username: "u2", initial: "U"},
        };
        const inviteState = {
            ...state,
            incoming_count: 2,
            items: [matchInvite, secondInvite],
        };
        setup({getJson: vi.fn().mockResolvedValue(inviteState), postJson: vi.fn()});
        await vi.advanceTimersByTimeAsync(0);

        const toasts = [...document.querySelectorAll(".notification-toast")];
        expect(toasts).toHaveLength(2);
        expect(toasts[0].textContent).toBe("challenger vừa mời bạn thi đấu");
        expect(toasts[1].textContent).toBe("u2 vừa mời bạn thi đấu");
    });

    it("opens with the trigger and Escape closes then restores focus", async () => {
        setup();
        await vi.advanceTimersByTimeAsync(0);
        const trigger = document.querySelector("[data-notification-trigger]");
        const panel = document.querySelector("[data-notification-panel]");

        expect(document.querySelectorAll(".notification-toast")).toHaveLength(1);
        trigger.click();
        expect(panel.hidden).toBe(false);
        expect(trigger.getAttribute("aria-expanded")).toBe("true");
        expect(document.querySelectorAll(".notification-toast")).toHaveLength(0);
        document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));

        expect(panel.hidden).toBe(true);
        expect(trigger.getAttribute("aria-expanded")).toBe("false");
        expect(document.activeElement).toBe(trigger);
    });

    it("closes on an outside click", async () => {
        setup();
        await vi.advanceTimersByTimeAsync(0);
        document.querySelector("[data-notification-trigger]").click();

        document.body.dispatchEvent(new MouseEvent("click", {bubbles: true}));

        expect(document.querySelector("[data-notification-panel]").hidden).toBe(true);
    });

    it("posts a known action once and navigates accept to a safe room URL", async () => {
        const api = {
            getJson: vi.fn().mockResolvedValue({...state, items: [incoming]}),
            postJson: vi.fn().mockResolvedValue({room_url: "/matches/rooms/NEW123/"}),
        };
        const {navigate} = setup(api);
        await vi.advanceTimersByTimeAsync(0);

        const accept = [...document.querySelectorAll("[data-notification-action]")]
            .find((button) => button.dataset.notificationAction === "ACCEPT");
        accept.click();
        accept.click();
        await vi.advanceTimersByTimeAsync(0);

        expect(api.postJson).toHaveBeenCalledTimes(1);
        expect(api.postJson).toHaveBeenCalledWith(
            "/matches/1/rematch/",
            {action: "accept"},
            "csrf",
            {signal: expect.any(AbortSignal)},
        );
        expect(navigate).toHaveBeenCalledWith("http://localhost:3000/matches/rooms/NEW123/");
    });

    it("shows an action error and restores buttons without discarding items", async () => {
        const api = {
            getJson: vi.fn().mockResolvedValue({...state, items: [incoming]}),
            postJson: vi.fn().mockRejectedValue(new Error("Lời mời không còn khả dụng")),
        };
        setup(api);
        await vi.advanceTimersByTimeAsync(0);
        const accept = [...document.querySelectorAll("[data-notification-action]")]
            .find((button) => button.dataset.notificationAction === "ACCEPT");

        accept.click();
        await vi.advanceTimersByTimeAsync(0);

        expect(accept.disabled).toBe(false);
        expect(document.querySelectorAll("[data-notification-key]")).toHaveLength(1);
        expect(document.querySelector("[data-notification-status]").textContent)
            .toBe("Lời mời không còn khả dụng");
    });

    it("keeps the last rendered data when a later response is invalid", async () => {
        const api = {
            getJson: vi.fn()
                .mockResolvedValueOnce(state)
                .mockResolvedValueOnce({...state, items: [{...incoming, context_url: "https://evil.test/"}]}),
            postJson: vi.fn(),
        };
        setup(api);
        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(5000);

        expect(document.querySelectorAll("[data-notification-key]")).toHaveLength(2);
        expect(document.querySelector("[data-notification-status]").textContent)
            .toBe("Dữ liệu có thể đã cũ");
    });

    it("uses the hidden polling interval and prevents overlapping requests", async () => {
        let resolve;
        const api = {
            getJson: vi.fn(() => new Promise((done) => { resolve = done; })),
            postJson: vi.fn(),
        };
        setup(api);
        await vi.advanceTimersByTimeAsync(0);
        expect(api.getJson).toHaveBeenCalledTimes(1);

        hiddenSpy.mockReturnValue(true);
        document.dispatchEvent(new Event("visibilitychange"));
        await vi.advanceTimersByTimeAsync(30000);
        expect(api.getJson).toHaveBeenCalledTimes(1);
        resolve(state);
        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(29999);
        expect(api.getJson).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(1);
        expect(api.getJson).toHaveBeenCalledTimes(2);
    });

    it("aborts a stalled request after five seconds without clearing old data", async () => {
        const api = {
            getJson: vi.fn()
                .mockResolvedValueOnce(state)
                .mockImplementationOnce(() => new Promise(() => {})),
            postJson: vi.fn(),
        };
        setup(api);
        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(5000);
        await vi.advanceTimersByTimeAsync(5000);

        expect(api.getJson.mock.calls[1][1].signal.aborted).toBe(true);
        expect(document.querySelectorAll("[data-notification-key]")).toHaveLength(2);
    });
});
