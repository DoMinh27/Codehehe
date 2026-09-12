import {describe, expect, it, vi} from "vitest";

import {createSkillController} from "./skill-controller.js";


function makeController(api) {
    document.body.innerHTML = `
        <p id="skill-notice"></p>
        <form id="typing-form"><button type="submit"></button></form>
        <input id="typing-input">
        <p id="typing-result"></p>
    `;
    const combatFeedback = {show: vi.fn(), showError: vi.fn()};
    const controller = createSkillController({
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
        combatFeedback,
    });
    return {combatFeedback, controller};
}


describe("skill controller", () => {
    it("suppresses duplicate use of the same skill", () => {
        const api = {postJson: vi.fn(() => new Promise(() => {}))};
        const {controller} = makeController(api);
        const button = document.createElement("button");

        const skill = {code: "BLUR", target_mode: "OPPONENT"};
        void controller.useSkill(skill, button);
        void controller.useSkill(skill, button);

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });

    it("uses the current player as the target for self skills", async () => {
        const api = {postJson: vi.fn().mockResolvedValue({
            feedback: {id: 1, text: "Khiên đã sẵn sàng"},
        })};
        const {combatFeedback, controller} = makeController(api);
        const button = document.createElement("button");

        await controller.useSkill({code: "PURIFY", target_mode: "SELF"}, button);

        expect(api.postJson).toHaveBeenCalledWith(
            "/skills/PURIFY",
            {target_player_id: 1, idempotency_key: "skill-1"},
            "csrf",
        );
        expect(combatFeedback.show).toHaveBeenCalledWith({
            id: 1,
            text: "Khiên đã sẵn sàng",
        });
    });

    it("shows a structured outcome after a successful skill use", async () => {
        const api = {
            postJson: vi.fn().mockResolvedValue({
                feedback: {
                    id: 3,
                    text: "Nhận được 1 lượt Che mờ đề",
                    cue: "STEAL_GAIN",
                    tone: "SUCCESS",
                },
            }),
        };
        const {combatFeedback, controller} = makeController(api);
        const button = document.createElement("button");

        await controller.useSkill({code: "STEAL", target_mode: "OPPONENT"}, button);

        expect(combatFeedback.show).toHaveBeenCalledWith({
            id: 3,
            text: "Nhận được 1 lượt Che mờ đề",
            cue: "STEAL_GAIN",
            tone: "SUCCESS",
        });
    });

    it("explains when an offensive skill is blocked by Shield", async () => {
        const api = {
            postJson: vi.fn().mockResolvedValue({
                feedback: {
                    id: 4,
                    text: "Đòn đã bị chặn",
                    cue: "SHIELD_BLOCKED_ATTACK",
                    tone: "WARNING",
                },
            }),
        };
        const {combatFeedback, controller} = makeController(api);
        const button = document.createElement("button");

        await controller.useSkill(
            {code: "MIRROR_CODE", target_mode: "OPPONENT"},
            button,
        );

        expect(combatFeedback.show).toHaveBeenCalledWith({
            id: 4,
            text: "Đòn đã bị chặn",
            cue: "SHIELD_BLOCKED_ATTACK",
            tone: "WARNING",
        });
    });

    it("suppresses duplicate typing completion", () => {
        const api = {postJson: vi.fn(() => new Promise(() => {}))};
        const {controller} = makeController(api);
        controller.bind();
        const form = document.getElementById("typing-form");

        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));

        expect(api.postJson).toHaveBeenCalledTimes(1);
    });
});
