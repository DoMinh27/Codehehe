import {beforeEach, describe, expect, it} from "vitest";

import {createDashboardRenderer} from "./dashboard-renderer.js";


function setup() {
    document.body.innerHTML = `
      <div id="operations-dashboard">
        <button id="ops-refresh" type="button"></button>
        <span id="ops-updated-at"></span>
        <p id="ops-stale-notice" hidden></p>
        <div id="ops-health"></div>
        <div id="ops-counters"></div>
        <div id="ops-alerts"></div>
        <div id="ops-live-matches"></div>
        <div id="ops-submissions"></div>
        <div id="ops-ai-reviews"></div>
        <div id="ops-kpis"></div>
      </div>
    `;
    const root = document.getElementById("operations-dashboard");
    return {root, renderer: createDashboardRenderer({root, documentRoot: document})};
}

function snapshot() {
    return {
        health: {
            web: {status: "ok", label: "Hoạt động", detail: "Ứng dụng phản hồi."},
            judge0: {status: "degraded", label: "Chậm", detail: "Phản hồi chậm."},
            ai_worker: {status: "unavailable", label: "Lỗi", detail: "Worker lỗi."},
        },
        counters: {
            waiting_matches: 2,
            playing_matches: 3,
            playing_players: 6,
            pending_submissions: 1,
            active_ai_reviews: 4,
            fair_play_flags: 1,
            alerts: 2,
        },
        alerts: [{
            severity: "critical",
            code: "STALE_SUBMISSIONS",
            message: "Submission bị treo <script>alert(1)</script>",
            count: 2,
            checked_at: "2026-08-10T10:00:00Z",
            url: "javascript:alert(1)",
        }],
        live_matches: [{
            room_code: "ABC123",
            players: [{username: "u1", score: 2}, {username: "admin", score: 1}],
            remaining_seconds: 91,
            pending_submissions: 1,
            status: "Đang chơi",
            url: "/admin/matches/match/1/change/",
        }],
        submissions: {
            total: 10,
            ac_rate: 50,
            pending: 1,
            stale: 0,
            average_latency_ms: 230,
            p95_latency_ms: 600,
            verdicts: [{code: "ACCEPTED", label: "Accepted", count: 5, percentage: 50}],
            internal_errors: [],
        },
        ai_reviews: {
            counts: {PENDING: 1, PROCESSING: 1, COMPLETED: 8, FAILED: 1},
            success_rate: 88.9,
            provider: "openrouter",
            configured_model: "openrouter/free",
            actual_model: "nvidia/model",
            tokens: {input: 100, output: 20, reasoning: 10},
            errors: [{code: "RATE_LIMIT", count: 1}],
        },
        kpis: {new_accounts: 2, active_players: 5, finished_matches: 4, cancelled_matches: 1},
    };
}


beforeEach(() => {
    document.body.innerHTML = "";
});


describe("operations dashboard renderer", () => {
    it("renders health, counters and operational details", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());

        expect(root.querySelector("#ops-health").textContent).toContain("Web App");
        expect(root.querySelectorAll('.ops-health-card[data-status="warning"]')).toHaveLength(1);
        expect(root.querySelectorAll('.ops-health-card[data-status="error"]')).toHaveLength(1);
        expect(root.querySelector("#ops-counters").textContent).toContain("Người chơi trong trận");
        expect(root.querySelector("#ops-counters").textContent).toContain("6");
        expect(root.querySelector("#ops-counters").textContent).toContain("Fair Play bị gắn cờ");
        expect(root.querySelector("#ops-live-matches").textContent).toContain("u1 2 — admin 1");
        expect(root.querySelector("#ops-submissions").textContent).toContain("50%");
        expect(root.querySelector("#ops-ai-reviews").textContent).toContain("openrouter/free");
    });

    it("uses text content and rejects unsafe links", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());

        const alert = root.querySelector(".ops-alert");
        expect(alert.tagName).toBe("ARTICLE");
        expect(alert.textContent).toContain("<script>alert(1)</script>");
        expect(alert.querySelector("script")).toBeNull();
        expect(root.querySelector(".ops-live-match").getAttribute("href"))
            .toBe("/admin/matches/match/1/change/");
    });

    it("keeps content while marking data stale and clears the warning on recovery", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());
        const before = root.querySelector("#ops-counters").textContent;

        renderer.setStale("Mất mạng.");

        expect(root.querySelector("#ops-stale-notice").hidden).toBe(false);
        expect(root.querySelector("#ops-stale-notice").textContent).toContain("Mất mạng");
        expect(root.querySelector("#ops-counters").textContent).toBe(before);

        renderer.setFresh("2026-08-10T10:00:00Z");
        expect(root.querySelector("#ops-stale-notice").hidden).toBe(true);
        expect(root.querySelector("#ops-updated-at").textContent).toContain("Cập nhật lúc");
    });
});
