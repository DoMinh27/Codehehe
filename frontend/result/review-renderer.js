const STATUS_MESSAGES = {
    ELIGIBLE: "Bài Accepted đã sẵn sàng để phân tích",
    NOT_ELIGIBLE: "Chưa có bài Accepted để phân tích",
    PENDING: "Đang chờ đến lượt phân tích AI",
    PROCESSING: "AI đang phân tích bài làm",
    FAILED: "Phân tích chưa thành công",
};

const STATUS_LABELS = {
    ELIGIBLE: "Accepted",
    NOT_ELIGIBLE: "Chưa đủ điều kiện",
    PENDING: "Đang chờ",
    PROCESSING: "Đang xử lý",
    COMPLETED: "Hoàn tất",
    FAILED: "Tạm thất bại",
};


function addList(documentRoot, parent, headingText, items, emptyText) {
    const section = documentRoot.createElement("section");
    section.className = "review-detail";
    const heading = documentRoot.createElement("h4");
    heading.textContent = headingText;
    section.appendChild(heading);
    if (items.length === 0) {
        const emptyMessage = documentRoot.createElement("p");
        emptyMessage.className = "muted";
        emptyMessage.textContent = emptyText;
        section.appendChild(emptyMessage);
        parent.appendChild(section);
        return;
    }
    const list = documentRoot.createElement("ul");
    for (const item of items) {
        const listItem = documentRoot.createElement("li");
        listItem.textContent = item;
        list.appendChild(listItem);
    }
    section.appendChild(list);
    parent.appendChild(section);
}


function renderCompleted(documentRoot, detail, analysis) {
    const summarySection = documentRoot.createElement("section");
    summarySection.className = "review-summary";
    const summaryHeading = documentRoot.createElement("h4");
    summaryHeading.textContent = "Tóm tắt cách làm";
    const summary = documentRoot.createElement("p");
    summary.textContent = analysis.approach_summary;
    summarySection.append(summaryHeading, summary);

    const complexityHeading = documentRoot.createElement("h4");
    complexityHeading.className = "complexity-heading";
    complexityHeading.textContent = "Độ phức tạp";
    const complexity = documentRoot.createElement("div");
    complexity.className = "complexity-badges";
    const time = documentRoot.createElement("span");
    time.textContent = `Thời gian ${analysis.time_complexity}`;
    const space = documentRoot.createElement("span");
    space.textContent = `Bộ nhớ ${analysis.space_complexity}`;
    complexity.append(time, space);
    detail.append(summarySection, complexityHeading, complexity);

    addList(documentRoot, detail, "Điểm tốt", analysis.strengths,
        "Không có điểm nổi bật được ghi nhận");
    addList(documentRoot, detail, "Điểm cần cải thiện", analysis.improvements,
        "Không có điểm cần cải thiện đáng kể");

    const betterSection = documentRoot.createElement("section");
    betterSection.className = "review-detail review-detail--better";
    const betterHeading = documentRoot.createElement("h4");
    betterHeading.textContent = "Hướng tiếp cận tốt hơn";
    const betterApproach = documentRoot.createElement("p");
    betterApproach.textContent = analysis.better_approach;
    betterSection.append(betterHeading, betterApproach);
    detail.appendChild(betterSection);
}


function createActionButton(documentRoot, review) {
    const button = documentRoot.createElement("button");
    button.type = "button";
    button.className = "ai-review-action";

    if (review.status === "COMPLETED") {
        button.textContent = "Xem phân tích";
        button.dataset.aiReviewToggle = "true";
        button.setAttribute("aria-expanded", "false");
        return button;
    }
    if (review.status === "ELIGIBLE") {
        button.textContent = "Phân tích AI";
        button.disabled = !review.can_request;
    } else if (review.status === "FAILED" && review.can_retry) {
        button.textContent = "Thử lại";
    } else if (review.status === "FAILED") {
        button.textContent = "Không thể phân tích";
        button.disabled = true;
    } else {
        button.textContent = review.status === "PROCESSING"
            ? "Đang xử lý"
            : review.status === "PENDING" ? "Đang chờ" : "Phân tích AI";
        button.disabled = true;
    }

    if (!button.disabled && review.request_url) {
        button.dataset.aiReviewRequest = review.request_url;
    }
    return button;
}


export function createReviewRenderer({documentRoot = document} = {}) {
    const list = documentRoot.getElementById("ai-review-list");
    const notice = documentRoot.getElementById("ai-review-notice");

    return {
        render(payload) {
            list.replaceChildren();
            notice.textContent = payload.terminal
                ? "Phân tích AI đã cập nhật"
                : "Một số bài đang được xử lý";
            notice.dataset.terminal = payload.terminal ? "true" : "false";

            for (const player of payload.players) {
                const playerSection = documentRoot.createElement("section");
                playerSection.className = "ai-review-player";
                const playerHeading = documentRoot.createElement("header");
                playerHeading.className = "ai-review-player__heading";
                const playerName = documentRoot.createElement("h3");
                playerName.textContent = player.username;
                playerHeading.appendChild(playerName);
                playerSection.appendChild(playerHeading);

                const reviewGrid = documentRoot.createElement("div");
                reviewGrid.className = "ai-review-grid";
                for (const review of player.reviews) {
                    const card = documentRoot.createElement("article");
                    card.className = "ai-review-card";
                    card.dataset.status = review.status;

                    const heading = documentRoot.createElement("div");
                    heading.className = "ai-review-card__heading";
                    const title = documentRoot.createElement("h4");
                    title.textContent = review.title;
                    const controls = documentRoot.createElement("div");
                    controls.className = "ai-review-card__controls";
                    const badge = documentRoot.createElement("span");
                    badge.className = `ai-status ai-status--${review.status.toLowerCase()}`;
                    badge.textContent = (
                        review.status === "FAILED" && !review.can_retry
                            ? "Không thể phân tích"
                            : STATUS_LABELS[review.status] || "Chưa xác định"
                    );
                    controls.append(badge, createActionButton(documentRoot, review));
                    heading.append(title, controls);
                    card.appendChild(heading);

                    if (review.status === "COMPLETED" && review.analysis) {
                        const detail = documentRoot.createElement("div");
                        detail.className = "ai-review-card__detail";
                        detail.hidden = true;
                        renderCompleted(documentRoot, detail, review.analysis);
                        card.appendChild(detail);
                    } else {
                        const message = documentRoot.createElement("p");
                        message.className = "ai-review-card__message";
                        message.textContent = STATUS_MESSAGES[review.status]
                            || "Trạng thái phân tích chưa xác định";
                        card.appendChild(message);
                    }
                    reviewGrid.appendChild(card);
                }
                playerSection.appendChild(reviewGrid);
                list.appendChild(playerSection);
            }
        },
        showTemporaryError(message) {
            notice.textContent = message;
            notice.dataset.terminal = "false";
        },
    };
}
