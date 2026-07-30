import {afterEach, describe, expect, it, vi} from "vitest";

import {createPolling} from "./polling.js";


afterEach(() => {
    vi.useRealTimers();
});


describe("createPolling", () => {
    it("uses visible and hidden polling intervals", async () => {
        vi.useFakeTimers();
        let hidden = false;
        const refresh = vi.fn().mockResolvedValue(undefined);
        const polling = createPolling({
            refresh,
            isHidden: () => hidden,
        });

        polling.start({immediate: false});
        await vi.advanceTimersByTimeAsync(1000);
        expect(refresh).toHaveBeenCalledTimes(1);

        hidden = true;
        await vi.advanceTimersByTimeAsync(4000);
        expect(refresh).toHaveBeenCalledTimes(2);
        polling.stop();
    });

    it("does not overlap refresh requests", async () => {
        let resolveRefresh;
        const refresh = vi.fn(() => new Promise((resolve) => {
            resolveRefresh = resolve;
        }));
        const polling = createPolling({refresh});

        polling.start();
        await polling.refresh();
        expect(refresh).toHaveBeenCalledTimes(1);
        resolveRefresh();
        polling.stop();
    });

    it("stops scheduled refreshes", async () => {
        vi.useFakeTimers();
        const refresh = vi.fn().mockResolvedValue(undefined);
        const polling = createPolling({refresh});

        polling.start({immediate: false});
        polling.stop();
        await vi.advanceTimersByTimeAsync(5000);

        expect(refresh).not.toHaveBeenCalled();
    });
});
