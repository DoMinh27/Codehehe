import {beforeEach, describe, expect, it} from "vitest";

import {createReviewRenderer} from "./review-renderer.js";


beforeEach(() => {
    document.body.innerHTML = `
        <p id="ai-review-notice"></p>
        <div id="ai-review-list"></div>
    `;
});


describe("AI review renderer", () => {
    it("renders completed analysis without rendering code fields", () => {
        const renderer = createReviewRenderer({documentRoot: document});
        renderer.render({
            terminal: true,
            players: [{
                username: "player",
                reviews: [{
                    title: "Bài 1",
                    status: "COMPLETED",
                    analysis: {
                        approach_summary: "Duyệt một lần.",
                        time_complexity: "O(n)",
                        space_complexity: "O(1)",
                        strengths: ["Rõ ràng"],
                        improvements: ["Tên biến"],
                        better_approach: "Giữ thuật toán.",
                    },
                }],
            }],
        });

        expect(document.body.textContent).toContain("Duyệt một lần.");
        expect(document.body.textContent).toContain("Độ phức tạp");
        expect(document.body.textContent).not.toContain("reference_solution");
        expect(document.querySelector("[data-status='COMPLETED']")).not.toBeNull();
        expect(document.querySelector(".ai-review-player .avatar")).toBeNull();
    });

    it("renders pending, failed, and not eligible statuses", () => {
        const renderer = createReviewRenderer({documentRoot: document});
        renderer.render({
            terminal: false,
            players: [{
                username: "player",
                reviews: [
                    {title: "A", status: "PENDING", analysis: null},
                    {title: "B", status: "FAILED", analysis: null},
                    {title: "C", status: "NOT_ELIGIBLE", analysis: null},
                ],
            }],
        });

        expect(document.body.textContent).toContain("Đang chờ phân tích AI");
        expect(document.body.textContent).toContain("Chưa thể phân tích");
        expect(document.body.textContent).toContain("Chưa có bài Accepted");
    });

    it("renders a clear message when there are no improvements", () => {
        const renderer = createReviewRenderer({documentRoot: document});
        renderer.render({
            terminal: true,
            players: [{
                username: "player",
                reviews: [{
                    title: "Tính tích hai số",
                    status: "COMPLETED",
                    analysis: {
                        approach_summary: "Đọc hai số và in ra tích.",
                        time_complexity: "O(1)",
                        space_complexity: "O(1)",
                        strengths: ["Lời giải đã tối ưu."],
                        improvements: [],
                        better_approach: "Không cần thay đổi.",
                    },
                }],
            }],
        });

        expect(document.body.textContent).toContain(
            "Không có điểm cần cải thiện đáng kể.",
        );
        expect(document.querySelectorAll("ul")).toHaveLength(1);
    });
});
