import {beforeEach, describe, expect, it, vi} from "vitest";

import {createSiteController} from "./site-main.js";


beforeEach(() => {
    document.body.innerHTML = "";
});


describe("site controller", () => {
    it("dismisses a message without submitting a form", () => {
        document.body.innerHTML = `
            <div class="alert"><span>Saved</span><button data-dismiss-alert>×</button></div>
        `;
        createSiteController({documentRoot: document, clipboard: {}}).start();

        document.querySelector("button").click();

        expect(document.querySelector(".alert")).toBeNull();
    });

    it("copies room code and reports success", async () => {
        document.body.innerHTML = `
            <strong id="room-code">AB12CD</strong>
            <button data-copy-target="#room-code" data-copy-status="#copy-status"></button>
            <span id="copy-status"></span>
        `;
        const clipboard = {writeText: vi.fn().mockResolvedValue(undefined)};
        createSiteController({documentRoot: document, clipboard}).start();

        document.querySelector("button").click();
        await vi.waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith("AB12CD"));

        expect(document.querySelector("#copy-status").textContent).toContain("Đã sao chép");
    });

    it("reports clipboard failure without breaking the page", async () => {
        document.body.innerHTML = `
            <strong id="room-code">AB12CD</strong>
            <button data-copy-target="#room-code" data-copy-status="#copy-status"></button>
            <span id="copy-status"></span>
        `;
        const clipboard = {writeText: vi.fn().mockRejectedValue(new Error("denied"))};
        createSiteController({documentRoot: document, clipboard}).start();

        document.querySelector("button").click();
        await vi.waitFor(() => {
            expect(document.querySelector("#copy-status").textContent)
                .toContain("Không thể sao chép");
        });
    });
});
