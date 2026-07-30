const STATUS_MESSAGES = {
    NOT_ELIGIBLE: "Chưa có bài Accepted để phân tích.",
    PENDING: "Đang chờ phân tích AI.",
    PROCESSING: "AI đang phân tích.",
    FAILED: "Chưa thể phân tích bài này.",
};

const STATUS_LABELS = {
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


function renderCompleted(documentRoot, card, analysis) {
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
    card.append(summarySection, complexityHeading, complexity);

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

    const betterSection = documentRoot.createElement("section");
    betterSection.className = "review-detail review-detail--better";
    const betterHeading = documentRoot.createElement("h4");
    betterHeading.textContent = "Hướng tiếp cận tốt hơn";
    const betterApproach = documentRoot.createElement("p");
    betterApproach.textContent = analysis.better_approach;
    betterSection.append(betterHeading, betterApproach);
    card.appendChild(betterSection);
}


function createPlayerHeading(documentRoot, username) {
    const heading = documentRoot.createElement("header");
    heading.className = "ai-review-player__heading";
    const avatar = documentRoot.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = username.slice(0, 1).toUpperCase();
    const title = documentRoot.createElement("h3");
    title.textContent = username;
    heading.append(avatar, title);
    return heading;
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
            notice.dataset.terminal = payload.terminal ? "true" : "false";

            for (const player of payload.players) {
                const playerSection = documentRoot.createElement("section");
                playerSection.className = "ai-review-player card";
                playerSection.appendChild(
                    createPlayerHeading(documentRoot, player.username),
                );

                const reviewGrid = documentRoot.createElement("div");
                reviewGrid.className = "ai-review-grid";
                for (const review of player.reviews) {
                    const card = documentRoot.createElement("article");
                    card.className = "ai-review-card";
                    card.dataset.status = review.status;

                    const cardHeading = documentRoot.createElement("header");
                    cardHeading.className = "ai-review-card__heading";
                    const title = documentRoot.createElement("h4");
                    title.textContent = review.title;
                    const statusBadge = documentRoot.createElement("span");
                    statusBadge.className = (
                        `ai-status ai-status--${review.status.toLowerCase()}`
                    );
                    statusBadge.textContent = (
                        STATUS_LABELS[review.status] || "Chưa xác định"
                    );
                    cardHeading.append(title, statusBadge);
                    card.appendChild(cardHeading);

                    if (review.status === "COMPLETED" && review.analysis) {
                        renderCompleted(documentRoot, card, review.analysis);
                    } else {
                        const status = documentRoot.createElement("p");
                        status.className = "ai-review-card__message";
                        status.textContent = (
                            STATUS_MESSAGES[review.status]
                            || "Trạng thái phân tích chưa xác định."
                        );
                        card.appendChild(status);
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
