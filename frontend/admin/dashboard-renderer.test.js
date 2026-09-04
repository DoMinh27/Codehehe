import {beforeEach, describe, expect, it} from "vitest";

import {createDashboardRenderer} from "./dashboard-renderer.js";


function setup() {
    document.body.innerHTML = `
      <div id="operations-dashboard">
        <button id="ops-refresh" type="button"></button>
        <span id="ops-updated-at"></span><p id="ops-stale-notice" hidden></p>
        <div id="ops-health-strip"></div><div id="ops-health-details"></div>
        <div id="ops-overview-counters"></div><div id="ops-alerts"></div>
        <div id="ops-overview-live"></div><span id="ops-overview-live-link"></span>
        <div id="ops-live-matches"></div><div id="ops-match-shortcuts"></div>
        <div id="ops-submissions"></div><div id="ops-ai-reviews"></div>
        <div id="ops-queue-shortcuts"></div><div id="ops-fair-play"></div>
        <div id="ops-system-shortcuts"></div><div id="ops-kpis"></div>
      </div>
    `;
    const root = document.getElementById("operations-dashboard");
    return {root, renderer: createDashboardRenderer({root, documentRoot: document})};
}

function snapshot() {
    return {
        health: {
            database: {status: "ok", label: "Hoạt động", detail: "Kết nối bình thường."},
            judge0: {status: "degraded", label: "Chậm", detail: "Phản hồi chậm."},
            ai_worker: {status: "unavailable", label: "Lỗi", detail: "Worker lỗi."},
            match_sweeper: {status: "disabled", label: "Đã tắt", detail: "Tắt theo cấu hình."},
        },
        counters: {playing_matches: 3, pending_submissions: 1, active_ai_reviews: 4, fair_play_flags: 1},
        alerts: [{
            severity: "critical", code: "STALE_SUBMISSIONS", message: "Submission <script>alert(1)</script>",
            count: 2, oldest_at: "2026-08-10T10:00:00Z", url: "javascript:alert(1)", action_label: "Xem hàng đợi",
        }],
        live_matches: [{
            room_code: "ABC123", players: [{username: "u1", score: 2}, {username: "admin", score: 1}],
            remaining_seconds: 91, pending_submissions: 1, status: "Đang chơi", timing_status: "RUNNING",
            fair_play_flag_count: 1, url: "/admin/matches/match/1/change/",
        }],
        submissions: {
            total: 10, ac_rate: 50, pending: 1, stale: 0, average_latency_ms: 230, p95_latency_ms: 600,
            verdicts: [{code: "ACCEPTED", label: "Accepted", count: 5, percentage: 50}], internal_errors: [],
        },
        ai_reviews: {
            counts: {PENDING: 1, PROCESSING: 1, COMPLETED: 8, FAILED: 1}, success_rate: 88.9,
            provider: "openrouter", configured_model: "openrouter/free", actual_model: "nvidia/model",
            tokens: {input: 100, output: 20, reasoning: 10}, errors: [{code: "RATE_LIMIT", count: 1}],
        },
        fair_play: {flagged_players: [{
            room_code: "ABC123", username: "u1", reason: "Vượt số lần vi phạm", strike_count: 2,
            away_duration_seconds: 11, paste_count: 1, flagged_at: "2026-08-10T10:00:00Z",
            url: "/admin/matches/matchintegritystate/1/change/", timeline_url: "/admin/matches/matchintegrityevent/",
        }]},
        links: {
            live_matches: {url: "/admin/matches/match/?status__exact=PLAYING"},
            waiting_matches: {url: "/admin/matches/match/?status__exact=WAITING"},
            overdue_matches: {url: "/admin/matches/match/?status__exact=PLAYING"},
            pending_submissions: {url: "/admin/matches/submission/?verdict__exact=PENDING"},
            ai_reviews: {url: "/admin/matches/submissionaireview/"},
            worker_heartbeats: {url: "/admin/operations/workerheartbeat/"},
        },
        kpis: {new_accounts: 2, active_players: 5, finished_matches: 4, cancelled_matches: 1},
    };
}


beforeEach(() => { document.body.innerHTML = ""; });


describe("operations dashboard renderer", () => {
    it("renders the V2 health strip, operational tabs and Fair Play data", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());

        expect(root.querySelector("#ops-health-strip").textContent).toContain("Database");
        expect(root.querySelector("#ops-health-strip").textContent).not.toContain("Web App");
        expect(root.querySelectorAll('.ops-health-card[data-status="warning"]')).toHaveLength(1);
        expect(root.querySelector("#ops-overview-counters").textContent).toContain("Trận đang chơi");
        expect(root.querySelector("#ops-live-matches").textContent).toContain("u1 2 — admin 1");
        expect(root.querySelector("#ops-live-matches").textContent).toContain("tín hiệu Fair Play");
        expect(root.querySelector("#ops-submissions").textContent).toContain("50%");
        expect(root.querySelector("#ops-ai-reviews").textContent).toContain("openrouter/free");
        expect(root.querySelector("#ops-fair-play").textContent).toContain("Vượt số lần vi phạm");
    });

    it("uses text content and rejects unsafe links", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());

        const alert = root.querySelector(".ops-alert");
        expect(alert.tagName).toBe("ARTICLE");
        expect(alert.textContent).toContain("<script>alert(1)</script>");
        expect(alert.querySelector("script")).toBeNull();
        expect(root.querySelector(".ops-live-match .ops-action-link").getAttribute("href"))
            .toBe("/admin/matches/match/1/change/");
    });

    it("keeps content while marking data stale and clears the warning on recovery", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());
        const before = root.querySelector("#ops-overview-counters").textContent;

        renderer.setStale("Mất mạng.");
        expect(root.querySelector("#ops-stale-notice").hidden).toBe(false);
        expect(root.querySelector("#ops-stale-notice").textContent).toContain("Mất mạng");
        expect(root.querySelector("#ops-overview-counters").textContent).toBe(before);

        renderer.setFresh("2026-08-10T10:00:00Z");
        expect(root.querySelector("#ops-stale-notice").hidden).toBe(true);
        expect(root.querySelector("#ops-updated-at").textContent).toContain("Cập nhật:");
    });

    it("keeps focus on an equivalent dashboard action after polling renders new data", () => {
        const {root, renderer} = setup();
        renderer.render(snapshot());
        const action = root.querySelector(".ops-live-match .ops-action-link");
        action.focus();

        renderer.render(snapshot());

        expect(document.activeElement).toBe(
            root.querySelector(".ops-live-match .ops-action-link"),
        );
    });
});
