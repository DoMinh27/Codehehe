import {describe, expect, it, vi} from "vitest";

import {createSubmissionController} from "./submission-controller.js";


function setup() {
    document.body.innerHTML = `
        <form class="submission-form" data-submit-url="/submit">
            <textarea name="source_code">print(1)</textarea>
            <button type="submit"></button>
            <p class="submission-result"></p>
        </form>
    `;
    let resolveRequest;
    const api = {
        postJson: vi.fn(() => new Promise((resolve) => {
            resolveRequest = resolve;
        })),
    };
    const controller = createSubmissionController({
        documentRoot: document,
        api,
        csrfToken: "csrf",
        randomUUID: () => "request-1",
        refreshState: vi.fn(),
    });
    controller.bind();
    return {
        api,
        form: document.querySelector("form"),
        source: document.querySelector("textarea"),
        resolveRequest,
        getResolveRequest: () => resolveRequest,
    };
}


describe("submission controller", () => {
    it("suppresses duplicate submissions while a request is active", () => {
        const {api, form} = setup();

        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });

    it("reuses an idempotency key after error and clears it on source edit", async () => {
        const {api, form, source, getResolveRequest} = setup();
        api.postJson.mockRejectedValueOnce(new Error("offline"));

        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        await Promise.resolve();
        await Promise.resolve();
        expect(form.dataset.idempotencyKey).toBe("request-1");

        source.dispatchEvent(new Event("input", {bubbles: true}));
        expect(form.dataset.idempotencyKey).toBeUndefined();
        getResolveRequest()?.();
    });
});
