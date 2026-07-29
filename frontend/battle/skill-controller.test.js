import {describe, expect, it, vi} from "vitest";

import {createSkillController} from "./skill-controller.js";


function makeController(api) {
    document.body.innerHTML = `
        <p id="skill-notice"></p>
        <form id="typing-form"><button type="submit"></button></form>
        <input id="typing-input">
        <p id="typing-result"></p>
    `;
    return createSkillController({
        documentRoot: document,
        api,
        config: {
            opponentPlayerId: 2,
            skillUseUrlTemplate: "/skills/__skill__",
            typingCompleteUrlTemplate: "/typing/__challenge__",
        },
        csrfToken: "csrf",
        randomUUID: () => "skill-1",
        refreshState: vi.fn(),
        getTypingChallengeId: () => 9,
        restoreSkillButton: vi.fn(),
    });
}


describe("skill controller", () => {
    it("suppresses duplicate use of the same skill", () => {
        const api = {postJson: vi.fn(() => new Promise(() => {}))};
        const controller = makeController(api);
        const button = document.createElement("button");

        void controller.useSkill("BLUR", button);
        void controller.useSkill("BLUR", button);

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });

    it("suppresses duplicate typing completion", () => {
        const api = {postJson: vi.fn(() => new Promise(() => {}))};
        const controller = makeController(api);
        controller.bind();
        const form = document.getElementById("typing-form");

        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });
});
