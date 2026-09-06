import {beforeEach, describe, expect, it, vi} from "vitest";

import {createSiteController} from "./site-main.js";


beforeEach(() => {
    document.body.innerHTML = "";
});


describe("site controller", () => {
    it("moves focus to a general auth alert", () => {
        document.body.innerHTML = `
            <form data-auth-form>
                <div tabindex="-1" data-auth-form-alert>Sai tài khoản</div>
                <input data-auth-input id="id_username">
            </form>
        `;

        createSiteController({documentRoot: document, clipboard: {}}).start();

        expect(document.activeElement).toBe(
            document.querySelector("[data-auth-form-alert]"),
        );
    });

    it("focuses the first invalid field when there is no general alert", () => {
        document.body.innerHTML = `
            <form data-auth-form>
                <input data-auth-input aria-invalid="true" id="id_email">
            </form>
        `;

        createSiteController({documentRoot: document, clipboard: {}}).start();

        expect(document.activeElement).toBe(document.querySelector("#id_email"));
    });

    it("clears a field error only after the edited value is locally valid", () => {
        document.body.innerHTML = `
            <form data-auth-form>
                <div class="form-field form-field--error">
                    <input data-auth-input required minlength="8" aria-invalid="true"
                           aria-describedby="id_password_help id_password_error" id="id_password">
                    <span id="id_password_help">Help</span>
                    <span id="id_password_error" data-auth-field-error>Error</span>
                </div>
            </form>
        `;
        createSiteController({documentRoot: document, clipboard: {}}).start();
        const input = document.querySelector("#id_password");

        input.value = "short";
        input.dispatchEvent(new Event("input", {bubbles: true}));
        expect(document.querySelector("[data-auth-field-error]")).not.toBeNull();

        input.value = "long-enough";
        input.dispatchEvent(new Event("input", {bubbles: true}));
        expect(document.querySelector("[data-auth-field-error]")).toBeNull();
        expect(input.hasAttribute("aria-invalid")).toBe(false);
        expect(input.getAttribute("aria-describedby")).toBe("id_password_help");
    });

    it("hides the general auth alert when a field is edited", () => {
        document.body.innerHTML = `
            <form data-auth-form>
                <div data-auth-form-alert>Sai tài khoản</div>
                <input data-auth-input id="id_username">
            </form>
        `;
        createSiteController({documentRoot: document, clipboard: {}}).start();

        document.querySelector("#id_username").dispatchEvent(
            new Event("input", {bubbles: true}),
        );

        expect(document.querySelector("[data-auth-form-alert]").hidden).toBe(true);
    });

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
