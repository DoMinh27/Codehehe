import {beforeEach, describe, expect, test} from "vitest";

import {bindMobileWorkspaceTabs} from "./battle-main.js";


describe("mobile battle workspace tabs", () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <article class="battle-problem">
                <div class="mobile-workspace-tabs">
                    <button data-mobile-pane="problem" aria-pressed="true">
                        Đề bài
                    </button>
                    <button data-mobile-pane="editor" aria-pressed="false">
                        Code
                    </button>
                </div>
                <section class="problem-content"></section>
                <div class="workspace-column"></div>
            </article>
        `;
        bindMobileWorkspaceTabs({documentRoot: document});
    });

    test("switches between problem and editor without changing battle data", () => {
        const problem = document.querySelector(".battle-problem");
        const problemButton = document.querySelector(
            "[data-mobile-pane='problem']",
        );
        const editorButton = document.querySelector(
            "[data-mobile-pane='editor']",
        );

        editorButton.click();
        expect(problem.classList.contains("mobile-show-editor")).toBe(true);
        expect(editorButton.getAttribute("aria-pressed")).toBe("true");
        expect(problemButton.getAttribute("aria-pressed")).toBe("false");

        problemButton.click();
        expect(problem.classList.contains("mobile-show-editor")).toBe(false);
        expect(problemButton.getAttribute("aria-pressed")).toBe("true");
    });
});
