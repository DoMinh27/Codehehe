const COUNTER_LABELS = {
    waiting_matches: "Phòng đang chờ",
    playing_matches: "Trận đang chơi",
    playing_players: "Người chơi trong trận",
    pending_submissions: "Submission pending",
    active_ai_reviews: "AI Review đang xử lý",
    fair_play_flags: "Fair Play bị gắn cờ",
    alerts: "Cảnh báo",
};

const KPI_LABELS = {
    new_accounts: "Tài khoản mới",
    active_players: "Người có hoạt động",
    finished_matches: "Trận hoàn thành",
    cancelled_matches: "Trận bị hủy",
};

const HEALTH_LABELS = {
    web: "Web App",
    database: "Database",
    judge0: "Judge0",
    ai_worker: "AI Worker",
    match_sweeper: "Match Sweeper",
};

const STATUS_LABELS = {
    ok: "Bình thường",
    healthy: "Bình thường",
    warning: "Cần chú ý",
    error: "Có lỗi",
    failed: "Có lỗi",
    disabled: "Đã tắt",
    unknown: "Chưa có dữ liệu",
};

const KNOWN_STATUSES = new Set(["ok", "warning", "error", "disabled", "unknown"]);


function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function formatNumber(value) {
    return new Intl.NumberFormat("vi-VN").format(number(value));
}

function formatPercent(value) {
    return `${number(value).toLocaleString("vi-VN", {maximumFractionDigits: 1})}%`;
}

function formatDateTime(value) {
    if (!value) {
        return "—";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "—";
    }
    return new Intl.DateTimeFormat("vi-VN", {
        dateStyle: "short",
        timeStyle: "medium",
    }).format(date);
}

function formatDuration(seconds) {
    const safeSeconds = Math.max(0, Math.floor(number(seconds)));
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function normalizeStatus(value) {
    const raw = String(value || "unknown").toLowerCase();
    if (raw === "healthy") {
        return "ok";
    }
    if (raw === "failed") {
        return "error";
    }
    if (raw === "unavailable") {
        return "error";
    }
    if (raw === "degraded") {
        return "warning";
    }
    return KNOWN_STATUSES.has(raw) ? raw : "unknown";
}

function safeInternalUrl(value) {
    return typeof value === "string" && value.startsWith("/") && !value.startsWith("//")
        ? value
        : null;
}

function element(documentRoot, tagName, className, text) {
    const node = documentRoot.createElement(tagName);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = String(text);
    }
    return node;
}

function appendDefinition(documentRoot, container, label, value) {
    const item = element(documentRoot, "div", "ops-definition");
    item.append(
        element(documentRoot, "dt", null, label),
        element(documentRoot, "dd", null, value),
    );
    container.append(item);
}

function createLinkOrArticle(documentRoot, url, className) {
    const safeUrl = safeInternalUrl(url);
    const item = element(documentRoot, safeUrl ? "a" : "article", className);
    if (safeUrl) {
        item.href = safeUrl;
    }
    return item;
}


export function createDashboardRenderer({root, documentRoot = document}) {
    const healthRoot = root.querySelector("#ops-health");
    const countersRoot = root.querySelector("#ops-counters");
    const alertsRoot = root.querySelector("#ops-alerts");
    const liveRoot = root.querySelector("#ops-live-matches");
    const submissionsRoot = root.querySelector("#ops-submissions");
    const aiRoot = root.querySelector("#ops-ai-reviews");
    const kpisRoot = root.querySelector("#ops-kpis");
    const updatedAt = root.querySelector("#ops-updated-at");
    const staleNotice = root.querySelector("#ops-stale-notice");
    const refreshButton = root.querySelector("#ops-refresh");

    function renderEmpty(container, message) {
        container.replaceChildren(element(documentRoot, "p", "ops-empty", message));
    }

    function renderHealth(health = {}) {
        const fragment = documentRoot.createDocumentFragment();
        for (const [key, item = {}] of Object.entries(health)) {
            const status = normalizeStatus(item.status);
            const card = element(documentRoot, "article", "ops-health-card");
            card.dataset.status = status;
            card.append(element(documentRoot, "span", "ops-status-dot"));
            card.firstChild.setAttribute("aria-hidden", "true");
            const content = element(documentRoot, "div");
            content.append(
                element(documentRoot, "strong", null, HEALTH_LABELS[key] || key),
                element(documentRoot, "p", null, item.label || STATUS_LABELS[status]),
                element(documentRoot, "small", "ops-muted", item.detail || STATUS_LABELS[status]),
            );
            card.append(content);
            card.setAttribute(
                "aria-label",
                `${HEALTH_LABELS[key] || key}: ${item.label || STATUS_LABELS[status]}`,
            );
            fragment.append(card);
        }
        if (!fragment.childNodes.length) {
            renderEmpty(healthRoot, "Chưa có dữ liệu trạng thái.");
            return;
        }
        healthRoot.replaceChildren(fragment);
    }

    function renderCounters(counters = {}, labels = COUNTER_LABELS, container = countersRoot) {
        const fragment = documentRoot.createDocumentFragment();
        for (const [key, label] of Object.entries(labels)) {
            const card = element(documentRoot, "article", "ops-counter-card");
            card.append(
                element(documentRoot, "span", null, label),
                element(documentRoot, "strong", null, formatNumber(counters[key])),
            );
            fragment.append(card);
        }
        container.replaceChildren(fragment);
    }

    function renderAlerts(alerts = []) {
        if (!alerts.length) {
            renderEmpty(alertsRoot, "Không có cảnh báo đang mở.");
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        for (const alert of alerts) {
            const item = createLinkOrArticle(documentRoot, alert.url, "ops-alert");
            item.dataset.severity = ["critical", "error", "warning", "info"]
                .includes(String(alert.severity).toLowerCase())
                ? String(alert.severity).toLowerCase()
                : "warning";
            const content = element(documentRoot, "div");
            content.append(
                element(documentRoot, "strong", null, alert.message || alert.code || "Cảnh báo"),
                element(documentRoot, "small", "ops-muted", formatDateTime(alert.checked_at)),
            );
            item.append(content);
            if (alert.count !== null && alert.count !== undefined) {
                item.append(element(documentRoot, "span", "ops-count-badge", formatNumber(alert.count)));
            }
            fragment.append(item);
        }
        alertsRoot.replaceChildren(fragment);
    }

    function renderLiveMatches(matches = []) {
        if (!matches.length) {
            renderEmpty(liveRoot, "Hiện không có trận đang diễn ra.");
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        for (const match of matches) {
            const item = createLinkOrArticle(documentRoot, match.url, "ops-live-match");
            const header = element(documentRoot, "div", "ops-live-match__header");
            header.append(
                element(documentRoot, "strong", "ops-room-code", match.room_code || "—"),
                element(documentRoot, "span", "ops-status-label", match.status || "Đang chơi"),
            );
            const players = Array.isArray(match.players) ? match.players : [];
            const versus = players.length
                ? players.map((player) => `${player.username || "—"} ${formatNumber(player.score)}`).join(" — ")
                : "Chưa có dữ liệu người chơi";
            const metadata = element(documentRoot, "div", "ops-live-match__meta");
            metadata.append(
                element(documentRoot, "span", null, versus),
                element(documentRoot, "span", null, `Còn ${formatDuration(match.remaining_seconds)}`),
                element(
                    documentRoot,
                    "span",
                    null,
                    `${formatNumber(match.pending_submissions)} submission pending`,
                ),
            );
            item.append(header, metadata);
            fragment.append(item);
        }
        liveRoot.replaceChildren(fragment);
    }

    function renderSubmissions(data = {}) {
        const summary = element(documentRoot, "dl", "ops-definition-grid");
        appendDefinition(documentRoot, summary, "Tổng lượt nộp", formatNumber(data.total));
        appendDefinition(documentRoot, summary, "Tỷ lệ AC", formatPercent(data.ac_rate));
        appendDefinition(documentRoot, summary, "Pending", formatNumber(data.pending));
        appendDefinition(documentRoot, summary, "Bị treo", formatNumber(data.stale));
        appendDefinition(
            documentRoot,
            summary,
            "Xử lý trung bình",
            data.average_latency_ms == null ? "—" : `${formatNumber(data.average_latency_ms)} ms`,
        );
        appendDefinition(
            documentRoot,
            summary,
            "p95",
            data.p95_latency_ms == null ? "—" : `${formatNumber(data.p95_latency_ms)} ms`,
        );

        const verdicts = element(documentRoot, "div", "ops-bars");
        for (const verdict of data.verdicts || []) {
            const row = element(documentRoot, "div", "ops-bar-row");
            const heading = element(documentRoot, "div", "ops-bar-row__heading");
            heading.append(
                element(documentRoot, "span", null, verdict.label || verdict.code || "Khác"),
                element(documentRoot, "span", null, `${formatNumber(verdict.count)} · ${formatPercent(verdict.percentage)}`),
            );
            const track = element(documentRoot, "div", "ops-bar-track");
            const bar = element(documentRoot, "span", "ops-bar-value");
            bar.style.width = `${Math.min(100, Math.max(0, number(verdict.percentage)))}%`;
            track.append(bar);
            row.append(heading, track);
            verdicts.append(row);
        }

        const errors = element(documentRoot, "div", "ops-sublist");
        errors.append(element(documentRoot, "h3", null, "Internal Error gần đây"));
        if (!(data.internal_errors || []).length) {
            errors.append(element(documentRoot, "p", "ops-empty", "Không có Internal Error gần đây."));
        } else {
            for (const error of data.internal_errors) {
                const item = createLinkOrArticle(documentRoot, error.url, "ops-sublist__item");
                item.append(
                    element(documentRoot, "strong", null, `#${error.id}`),
                    element(
                        documentRoot,
                        "span",
                        null,
                        `${error.match_code || "—"} · ${error.player || "—"} · ${error.problem || "—"}`,
                    ),
                    element(documentRoot, "time", null, formatDateTime(error.received_at)),
                );
                errors.append(item);
            }
        }
        submissionsRoot.replaceChildren(summary, verdicts, errors);
    }

    function renderAIReviews(data = {}) {
        const counts = data.counts || {};
        const summary = element(documentRoot, "dl", "ops-definition-grid");
        for (const status of ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]) {
            appendDefinition(
                documentRoot,
                summary,
                status.charAt(0) + status.slice(1).toLowerCase(),
                formatNumber(counts[status] ?? counts[status.toLowerCase()]),
            );
        }
        appendDefinition(documentRoot, summary, "Tỷ lệ thành công", formatPercent(data.success_rate));
        appendDefinition(documentRoot, summary, "Job cũ nhất", formatDateTime(data.oldest_eligible_at));
        appendDefinition(documentRoot, summary, "Hoàn thành gần nhất", formatDateTime(data.last_completed_at));

        const provider = element(documentRoot, "dl", "ops-definition-grid ops-definition-grid--compact");
        appendDefinition(documentRoot, provider, "Provider", data.provider || "—");
        appendDefinition(documentRoot, provider, "Model cấu hình", data.configured_model || "—");
        appendDefinition(documentRoot, provider, "Model thực tế", data.actual_model || "—");
        appendDefinition(documentRoot, provider, "Input tokens", formatNumber(data.tokens?.input));
        appendDefinition(documentRoot, provider, "Output tokens", formatNumber(data.tokens?.output));
        appendDefinition(documentRoot, provider, "Reasoning tokens", formatNumber(data.tokens?.reasoning));

        const errors = element(documentRoot, "div", "ops-sublist");
        errors.append(element(documentRoot, "h3", null, "Mã lỗi phổ biến"));
        if (!(data.errors || []).length) {
            errors.append(element(documentRoot, "p", "ops-empty", "Không có lỗi trong 24 giờ."));
        } else {
            for (const error of data.errors) {
                const item = element(documentRoot, "div", "ops-sublist__item");
                item.append(
                    element(documentRoot, "code", null, error.code || "UNKNOWN"),
                    element(documentRoot, "strong", null, formatNumber(error.count)),
                );
                errors.append(item);
            }
        }
        aiRoot.replaceChildren(summary, provider, errors);
    }

    return {
        render(payload = {}) {
            renderHealth(payload.health);
            renderCounters(payload.counters);
            renderAlerts(payload.alerts);
            renderLiveMatches(payload.live_matches);
            renderSubmissions(payload.submissions);
            renderAIReviews(payload.ai_reviews);
            renderCounters(payload.kpis, KPI_LABELS, kpisRoot);
        },
        setFresh(generatedAt) {
            staleNotice.hidden = true;
            staleNotice.textContent = "";
            updatedAt.textContent = generatedAt
                ? `Cập nhật lúc ${formatDateTime(generatedAt)}`
                : "Dữ liệu ban đầu";
        },
        setStale(message) {
            staleNotice.hidden = false;
            staleNotice.textContent = `Dữ liệu có thể đã cũ. ${message}`;
        },
        setRefreshing(refreshing) {
            refreshButton.disabled = refreshing;
            refreshButton.setAttribute("aria-busy", refreshing ? "true" : "false");
            refreshButton.textContent = refreshing ? "Đang cập nhật…" : "Làm mới";
        },
    };
}
