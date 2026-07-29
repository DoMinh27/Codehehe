import {describe, expect, it} from "vitest";

import {typingActionLocked, typingSecondsRemaining} from "./typing.js";


describe("Typing challenge state", () => {
    it("counts down from authoritative server time", () => {
        expect(typingSecondsRemaining(
            {expires_at: "2026-07-29T00:00:20Z"},
            "2026-07-29T00:00:05Z",
        )).toBe(15);
    });

    it("unlocks an expired challenge", () => {
        const payload = {
            my_action_locked: true,
            server_time: "2026-07-29T00:00:20Z",
            typing_challenge: {expires_at: "2026-07-29T00:00:20Z"},
        };
        expect(typingActionLocked(payload)).toBe(false);
        expect(typingSecondsRemaining(
            payload.typing_challenge,
            payload.server_time,
        )).toBe(0);
    });
});
