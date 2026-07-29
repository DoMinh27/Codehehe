import {describe, expect, it} from "vitest";

import {activeEffectCodes, newestSkillUseId} from "./effects.js";


describe("Skill effect state", () => {
    it("keeps only server effects that have not expired", () => {
        const now = Date.parse("2026-07-28T10:00:00Z");
        const codes = activeEffectCodes(
            [
                {
                    code: "MIRROR_CODE",
                    expires_at: "2026-07-28T10:00:01Z",
                },
                {
                    code: "BLUR_STATEMENT",
                    expires_at: "2026-07-28T09:59:59Z",
                },
            ],
            now,
        );

        expect([...codes]).toEqual(["MIRROR_CODE"]);
    });

    it("finds the newest public Skill use", () => {
        expect(newestSkillUseId([{id: 2}, {id: 9}, {id: 5}])).toBe(9);
    });
});
