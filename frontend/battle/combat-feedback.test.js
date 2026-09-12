import {afterEach, beforeEach, describe, expect, test, vi} from "vitest";

import {createCombatFeedback} from "./combat-feedback.js";


describe("combat feedback", () => {
    let feedback;

    beforeEach(() => {
        vi.useFakeTimers();
        document.body.innerHTML = `
            <p id="skill-notice" hidden></p>
            <div id="skill-list"></div>
            <div class="duel-player--mine"></div>
            <strong id="match-timer"></strong>
            <div id="my-active-effects"></div>
        `;
        feedback = createCombatFeedback({
            documentRoot: document,
            windowObject: window,
        });
    });

    afterEach(() => {
        feedback.destroy();
        vi.useRealTimers();
    });

    test("uses the first state only as a baseline", () => {
        feedback.ingest([{id: 3, text: "Khiên đã sẵn sàng"}]);

        expect(document.getElementById("skill-notice").hidden).toBe(true);

        feedback.ingest([{
            id: 4,
            text: "Đòn đã bị chặn",
            cue: "SHIELD_BLOCKED_ATTACK",
            tone: "WARNING",
        }]);

        const notice = document.getElementById("skill-notice");
        expect(notice.hidden).toBe(false);
        expect(notice.textContent).toBe("Đòn đã bị chặn");
        expect(notice.dataset.tone).toBe("WARNING");
    });

    test("does not repeat POST feedback when polling returns the same id", () => {
        const item = {
            id: 8,
            text: "Đã dùng Đảo chiều code",
            cue: "SKILL_USED",
            tone: "SUCCESS",
        };
        feedback.show(item);
        feedback.ingest([item]);

        expect(document.getElementById("skill-notice").textContent).toBe(item.text);
        vi.advanceTimersByTime(2800);
        expect(document.getElementById("skill-notice").hidden).toBe(true);
    });

    test("keeps at most three messages including the active one", () => {
        feedback.show({text: "Một"});
        feedback.show({text: "Hai"});
        feedback.show({text: "Ba"});
        feedback.show({text: "Bốn"});

        expect(document.getElementById("skill-notice").textContent).toBe("Một");
        vi.advanceTimersByTime(2800);
        expect(document.getElementById("skill-notice").textContent).toBe("Ba");
        vi.advanceTimersByTime(2800);
        expect(document.getElementById("skill-notice").textContent).toBe("Bốn");
    });

    test("plays and clears an allowlisted visual cue", () => {
        const target = document.getElementById("match-timer");
        feedback.show({
            id: 9,
            text: "Bạn bị trừ 60 giây",
            cue: "TIME_DRAIN_HIT",
            tone: "WARNING",
        });

        expect(target.classList.contains("combat-cue--time")).toBe(true);
        vi.advanceTimersByTime(700);
        expect(target.classList.contains("combat-cue--time")).toBe(false);
    });
});
