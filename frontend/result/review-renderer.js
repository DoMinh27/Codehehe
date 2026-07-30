const STATUS_MESSAGES = {
    NOT_ELIGIBLE: "Chưa có bài Accepted để phân tích.",
    PENDING: "Đang chờ phân tích AI.",
    PROCESSING: "AI đang phân tích.",
    FAILED: "Chưa thể phân tích bài này.",
};


function addList(documentRoot, parent, headingText, items, emptyText) {
    const heading = documentRoot.createElement("h4");
    heading.textContent = headingText;
    if (items.length === 0) {
        const emptyMessage = documentRoot.createElement("p");
        emptyMessage.textContent = emptyText;
        parent.append(heading, emptyMessage);
        return;
    }
    const list = documentRoot.createElement("ul");
    for (const item of items) {
        const listItem = documentRoot.createElement("li");
        listItem.textContent = item;
        list.append(listItem);
    }
    parent.append(heading, list);
}


function renderCompleted(documentRoot, card, analysis) {
    const summary = documentRoot.createElement("p");
    summary.textContent = analysis.approach_summary;
    const complexity = documentRoot.createElement("p");
    complexity.textContent =
        `Độ phức tạp: thời gian ${analysis.time_complexity}; `
        + `bộ nhớ ${analysis.space_complexity}.`;
    card.append(summary, complexity);
    addList(
        documentRoot,
        card,
        "Điểm tốt",
        analysis.strengths,
        "Không có điểm nổi bật được ghi nhận.",
    );
    addList(
        documentRoot,
        card,
        "Điểm cần cải thiện",
        analysis.improvements,
        "Không có điểm cần cải thiện đáng kể.",
    );
    const betterHeading = documentRoot.createElement("h4");
    betterHeading.textContent = "Hướng tiếp cận tốt hơn";
    const betterApproach = documentRoot.createElement("p");
    betterApproach.textContent = analysis.better_approach;
    card.append(betterHeading, betterApproach);
}


export function createReviewRenderer({documentRoot = document} = {}) {
    const list = documentRoot.getElementById("ai-review-list");
    const notice = documentRoot.getElementById("ai-review-notice");

    return {
        render(payload) {
            list.replaceChildren();
            notice.textContent = payload.terminal
                ? "Phân tích AI đã cập nhật."
                : "Một số bài đang được xử lý.";
            for (const player of payload.players) {
                const playerSection = documentRoot.createElement("section");
                playerSection.className = "ai-review-player";
                const playerHeading = documentRoot.createElement("h3");
                playerHeading.textContent = player.username;
                playerSection.append(playerHeading);

                for (const review of player.reviews) {
                    const card = documentRoot.createElement("article");
                    card.className = "ai-review-card";
                    card.dataset.status = review.status;
                    const title = documentRoot.createElement("h4");
                    title.textContent = review.title;
                    card.append(title);
                    if (review.status === "COMPLETED" && review.analysis) {
                        renderCompleted(documentRoot, card, review.analysis);
                    } else {
                        const status = documentRoot.createElement("p");
                        status.textContent =
                            STATUS_MESSAGES[review.status]
                            || "Trạng thái phân tích chưa xác định.";
                        card.append(status);
                    }
                    playerSection.append(card);
                }
                list.append(playerSection);
            }
        },
        showTemporaryError(message) {
            notice.textContent = message;
        },
    };
}
