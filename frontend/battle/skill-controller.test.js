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
            currentPlayerId: 1,
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

        const skill = {code: "BLUR", target_mode: "OPPONENT"};
        void controller.useSkill(skill, button);
        void controller.useSkill(skill, button);

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });

    it("uses the current player as the target for self skills", async () => {
        const api = {postJson: vi.fn().mockResolvedValue({outcome: {}})};
        const controller = makeController(api);
        const button = document.createElement("button");

        await controller.useSkill({code: "PURIFY", target_mode: "SELF"}, button);

        expect(api.postJson).toHaveBeenCalledWith(
            "/skills/PURIFY",
            {target_player_id: 1, idempotency_key: "skill-1"},
            "csrf",
        );
    });

    it("shows a structured outcome after a successful skill use", async () => {
        const api = {
            postJson: vi.fn().mockResolvedValue({
                outcome: {
                    kind: "STOLEN_SKILL",
                    skill_name: "Làm mờ đề",
                },
            }),
        };
        const controller = makeController(api);
        const button = document.createElement("button");

        await controller.useSkill({code: "STEAL", target_mode: "OPPONENT"}, button);

        expect(document.getElementById("skill-notice").textContent).toBe(
            "Đã đánh cắp: Làm mờ đề.",
        );
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
