import {describe, expect, it, vi} from "vitest";

import {ApiError, createBattleApi} from "./api.js";


function response({ok = true, status = 200, payload = {}} = {}) {
    return {
        ok,
        status,
        json: vi.fn().mockResolvedValue(payload),
    };
}


describe("createBattleApi", () => {
    it("returns a successful JSON payload", async () => {
        const fetchImpl = vi.fn().mockResolvedValue(
            response({payload: {status: "PLAYING"}}),
        );
        const api = createBattleApi({fetchImpl});

        await expect(api.getJson("/state")).resolves.toEqual({
            status: "PLAYING",
        });
    });

    it("uses the stable backend code and message", async () => {
        const fetchImpl = vi.fn().mockResolvedValue(response({
            ok: false,
            status: 409,
            payload: {
                code: "MATCH_STATE_CONFLICT",
                message: "Trận đấu đã kết thúc.",
            },
        }));
        const api = createBattleApi({fetchImpl});

        await expect(api.post("/finalize", "csrf")).rejects.toMatchObject({
            code: "MATCH_STATE_CONFLICT",
            message: "Trận đấu đã kết thúc.",
            status: 409,
        });
    });

    it("maps a non-JSON response to INVALID_RESPONSE", async () => {
        const invalidResponse = response();
        invalidResponse.json.mockRejectedValue(new SyntaxError("Unexpected"));
        const api = createBattleApi({
            fetchImpl: vi.fn().mockResolvedValue(invalidResponse),
        });

        await expect(api.getJson("/state")).rejects.toMatchObject({
            code: "INVALID_RESPONSE",
        });
    });

    it("maps a fetch failure to NETWORK_ERROR", async () => {
        const api = createBattleApi({
            fetchImpl: vi.fn().mockRejectedValue(new TypeError("offline")),
        });

        await expect(api.getJson("/state")).rejects.toEqual(
            expect.any(ApiError),
        );
        await expect(api.getJson("/state")).rejects.toMatchObject({
            code: "NETWORK_ERROR",
        });
    });
});
