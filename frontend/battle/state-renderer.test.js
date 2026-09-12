import {beforeEach, describe, expect, test, vi} from "vitest";

import {createStateRenderer} from "./state-renderer.js";


function battleState(overrides = {}) {
    return {
        status: "PLAYING",
        server_time: "2026-09-12T10:00:00Z",
        remaining_seconds: 120,
        opponent_remaining_seconds: 120,
        my_timed_out: false,
        my_score: 0,
        opponent_score: 0,
        my_energy: 1,
        my_action_locked: false,
        typing_challenge: null,
        my_skills: [],
        active_effects: [],
        combat_notifications: [],
        my_solved_problem_ids: [],
        opponent_solved_problem_ids: [],
        first_solvers: {},
        ...overrides,
    };
}


describe("battle state renderer", () => {
    let combatFeedback;
    let editorRegistry;
    let nowMs;

    beforeEach(() => {
        nowMs = Date.parse("2026-09-12T10:00:00Z");
        document.body.innerHTML = `
            <strong id="match-timer"></strong>
            <strong id="opponent-timer"></strong>
            <strong id="my-score"></strong>
            <strong id="opponent-score"></strong>
            <span id="my-energy"></span>
            <div id="my-active-effects" hidden></div>
            <div id="skill-list" data-icon-sprite-url="/static/icons.svg">
                <div data-skill-group="DEFENSIVE"></div>
                <div data-skill-group="OFFENSIVE"></div>
            </div>
            <section id="typing-challenge" hidden>
                <code id="typing-prompt"></code>
                <span id="typing-countdown"></span>
                <input id="typing-input">
                <p id="typing-result"></p>
            </section>
            <div id="battle-problems"></div>
        `;
        combatFeedback = {ingest: vi.fn()};
        editorRegistry = {
            setEditable: vi.fn(),
            setMirrored: vi.fn(),
        };
    });

    test("renders and locally counts down active effects for only this player", () => {
        const renderer = createStateRenderer({
            documentRoot: document,
            now: () => nowMs,
            config: {currentPlayerId: 1, opponentPlayerId: 2},
            editorRegistry,
            combatFeedback,
            onUseSkill: vi.fn(),
            onFinalize: vi.fn(),
        });
        renderer.render(battleState({
            active_effects: [{
                id: 4,
                code: "SHIELD",
                name: "Khiên",
                started_at: "2026-09-12T10:00:00Z",
                expires_at: "2026-09-12T10:00:45Z",
            }],
            combat_notifications: [{id: 7, text: "Khiên đã sẵn sàng"}],
        }));

        const effects = document.getElementById("my-active-effects");
        expect(effects.hidden).toBe(false);
        expect(effects.textContent).toContain("Khiên 45s");
        expect(effects.querySelector("use").getAttribute("href")).toBe(
            "/static/icons.svg#icon-guard",
        );
        expect(combatFeedback.ingest).toHaveBeenCalledWith([
            {id: 7, text: "Khiên đã sẵn sàng"},
        ]);

        nowMs += 5000;
        renderer.renderTimer();
        expect(effects.textContent).toContain("Khiên 40s");

        nowMs += 40000;
        renderer.renderTimer();
        expect(effects.hidden).toBe(true);
        renderer.destroy();
    });
});
