import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {createDashboardController} from "./dashboard-controller.js";


function jsonResponse(payload, {status = 200, contentType = "application/json"} = {}) {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: {get: vi.fn().mockReturnValue(contentType)},
        json: vi.fn().mockResolvedValue(payload),
    };
}

function setup({fetchImpl = vi.fn(), rendererOverrides = {}} = {}) {
    document.body.innerHTML = `
        <div id="operations-dashboard"
             data-state-url="/admin/dashboard/state/"
             data-refresh-ms="15000"
             data-hidden-refresh-ms="60000"
             data-request-timeout-ms="5000">
          <button id="ops-refresh" type="button">Làm mới</button>
        </div>
    `;
    const renderer = {
        render: vi.fn(),
        setFresh: vi.fn(),
        setStale: vi.fn(),
        setRefreshing: vi.fn(),
        ...rendererOverrides,
    };
    const root = document.getElementById("operations-dashboard");
    const controller = createDashboardController({
        root,
        renderer,
        fetchImpl,
        documentRoot: document,
        windowObject: window,
    });
    return {controller, fetchImpl, renderer, root};
}


beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(document, "hidden", {configurable: true, value: false});
});

afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
});


describe("operations dashboard controller", () => {
    it("polls every 15 seconds while the page is visible", async () => {
        const payload = {generated_at: "2026-08-10T10:00:00Z"};
        const {controller, fetchImpl, renderer} = setup({
            fetchImpl: vi.fn().mockResolvedValue(jsonResponse(payload)),
        });
        controller.start({generated_at: "2026-08-10T09:59:00Z"});

        await vi.advanceTimersByTimeAsync(15000);

        expect(fetchImpl).toHaveBeenCalledTimes(1);
        expect(fetchImpl).toHaveBeenCalledWith(
            "/admin/dashboard/state/",
            expect.objectContaining({credentials: "same-origin"}),
        );
        expect(renderer.render).toHaveBeenLastCalledWith(payload);
        expect(renderer.setFresh).toHaveBeenLastCalledWith(payload.generated_at);
        controller.stop();
    });

    it("uses the slower interval while the page is hidden", async () => {
        Object.defineProperty(document, "hidden", {configurable: true, value: true});
        const {controller, fetchImpl} = setup({
            fetchImpl: vi.fn().mockResolvedValue(jsonResponse({generated_at: null})),
        });
        controller.start({});

        await vi.advanceTimersByTimeAsync(59999);
        expect(fetchImpl).not.toHaveBeenCalled();
        await vi.advanceTimersByTimeAsync(1);
        expect(fetchImpl).toHaveBeenCalledTimes(1);
        controller.stop();
    });

    it("adds refresh=1 only to a manual refresh", async () => {
        const {controller, fetchImpl, root} = setup({
            fetchImpl: vi.fn().mockResolvedValue(jsonResponse({generated_at: null})),
        });
        controller.start({});

        root.querySelector("#ops-refresh").click();
        await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));

        expect(fetchImpl.mock.calls[0][0]).toBe("/admin/dashboard/state/?refresh=1");
        controller.stop();
    });

    it("does not overlap requests", async () => {
        let resolveFetch;
        const fetchImpl = vi.fn(() => new Promise((resolve) => {
            resolveFetch = resolve;
        }));
        const {controller} = setup({fetchImpl});
        controller.start({});

        const first = controller.refresh();
        const second = controller.refresh();

        expect(fetchImpl).toHaveBeenCalledTimes(1);
        resolveFetch(jsonResponse({generated_at: null}));
        await Promise.all([first, second]);
        controller.stop();
    });

    it("keeps the previous render and marks data stale for non-JSON", async () => {
        const {controller, renderer} = setup({
            fetchImpl: vi.fn().mockResolvedValue(
                jsonResponse({}, {contentType: "text/html"}),
            ),
        });
        const initial = {generated_at: "2026-08-10T10:00:00Z", counters: {}};
        controller.start(initial);
        await controller.refresh();

        expect(renderer.render).toHaveBeenCalledTimes(1);
        expect(renderer.render).toHaveBeenCalledWith(initial);
        expect(renderer.setStale).toHaveBeenCalledWith("Phản hồi không phải JSON.");
        controller.stop();
    });

    it("aborts a request after five seconds and retries later", async () => {
        const fetchImpl = vi.fn((_url, options) => new Promise((_resolve, reject) => {
            options.signal.addEventListener("abort", () => {
                reject(new DOMException("Aborted", "AbortError"));
            });
        }));
        const {controller, renderer} = setup({fetchImpl});
        controller.start({});

        const request = controller.refresh();
        await vi.advanceTimersByTimeAsync(5000);
        await request;

        expect(renderer.setStale).toHaveBeenCalledWith(
            "Yêu cầu cập nhật đã quá thời gian chờ.",
        );
        controller.stop();
    });
});

