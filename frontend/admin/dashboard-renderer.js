const OVERVIEW_COUNTERS = {
    playing_matches: "Trận đang chơi",
    pending_submissions: "Submission pending",
    active_ai_reviews: "AI Review đang xử lý",
    fair_play_flags: "Fair Play cần xem xét",
};

const KPI_LABELS = {
    new_accounts: "Tài khoản mới",
    active_players: "Người có hoạt động",
    finished_matches: "Trận hoàn thành",
    cancelled_matches: "Trận bị hủy",
};

const HEALTH_LABELS = {
    database: "Database",
    judge0: "Judge0",
    ai_worker: "AI Worker",
    match_sweeper: "Match Sweeper",
};

const STATUS_LABELS = {
    ok: "Bình thường",
    warning: "Cần chú ý",
    error: "Không khả dụng",
    disabled: "Đã tắt",
    unknown: "Chưa có dữ liệu",
};

const STATUS_KEYS = Object.keys(HEALTH_LABELS);
const SEVERITY_LABELS = {
    critical: "Nghiêm trọng",
    warning: "Cần chú ý",
    info: "Thông tin",
};

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
    return `${String(Math.floor(safeSeconds / 60)).padStart(2, "0")}:${String(safeSeconds % 60).padStart(2, "0")}`;
}

function normalizeStatus(value) {
    const raw = String(value || "unknown").toLowerCase();
    if (raw === "healthy") {
        return "ok";
    }
    if (["failed", "unavailable", "error"].includes(raw)) {
        return "error";
    }
    if (raw === "degraded") {
        return "warning";
    }
    return Object.hasOwn(STATUS_LABELS, raw) ? raw : "unknown";
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

function actionLink(documentRoot, url, label) {
    const safeUrl = safeInternalUrl(url);
    if (!safeUrl) {
        return null;
    }
    const link = element(documentRoot, "a", "ops-action-link", label);
    link.href = safeUrl;
    link.dataset.opsFocusKey = `${safeUrl}|${label}`;
    return link;
}


export function createDashboardRenderer({root, documentRoot = document}) {
    const healthStripRoot = root.querySelector("#ops-health-strip");
    const healthDetailsRoot = root.querySelector("#ops-health-details");
    const countersRoot = root.querySelector("#ops-overview-counters");
    const alertsRoot = root.querySelector("#ops-alerts");
    const overviewLiveRoot = root.querySelector("#ops-overview-live");
    const overviewLiveLinkRoot = root.querySelector("#ops-overview-live-link");
    const liveRoot = root.querySelector("#ops-live-matches");
    const matchShortcutsRoot = root.querySelector("#ops-match-shortcuts");
    const submissionsRoot = root.querySelector("#ops-submissions");
    const aiRoot = root.querySelector("#ops-ai-reviews");
    const queueShortcutsRoot = root.querySelector("#ops-queue-shortcuts");
    const fairPlayRoot = root.querySelector("#ops-fair-play");
    const systemShortcutsRoot = root.querySelector("#ops-system-shortcuts");
    const kpisRoot = root.querySelector("#ops-kpis");
    const updatedAt = root.querySelector("#ops-updated-at");
    const staleNotice = root.querySelector("#ops-stale-notice");
    const refreshButton = root.querySelector("#ops-refresh");

    function renderEmpty(container, message) {
        container?.replaceChildren(element(documentRoot, "p", "ops-empty", message));
    }

    function buildHealthCard(key, item = {}, className) {
        const status = normalizeStatus(item.status);
        const card = element(documentRoot, "article", className);
        card.dataset.status = status;
        const dot = element(documentRoot, "span", "ops-status-dot");
        dot.setAttribute("aria-hidden", "true");
        const content = element(documentRoot, "div");
        content.append(
            element(documentRoot, "strong", null, HEALTH_LABELS[key] || key),
            element(documentRoot, "p", null, item.label || STATUS_LABELS[status]),
            element(documentRoot, "small", "ops-muted", item.detail || STATUS_LABELS[status]),
        );
        if (item.latency_ms !== undefined && item.latency_ms !== null) {
            content.append(element(documentRoot, "small", "ops-health-latency", `${formatNumber(item.latency_ms)} ms`));
        }
        card.append(dot, content);
        card.setAttribute("aria-label", `${HEALTH_LABELS[key] || key}: ${item.label || STATUS_LABELS[status]}`);
        return card;
    }

    function renderHealth(health = {}) {
        const strip = documentRoot.createDocumentFragment();
        const details = documentRoot.createDocumentFragment();
        for (const key of STATUS_KEYS) {
            const item = health[key] || {};
            strip.append(buildHealthCard(key, item, "ops-health-strip__item"));
            details.append(buildHealthCard(key, item, "ops-health-card"));
        }
        healthStripRoot?.replaceChildren(strip);
        healthDetailsRoot?.replaceChildren(details);
    }

    function renderCounters(counters = {}) {
        const fragment = documentRoot.createDocumentFragment();
        for (const [key, label] of Object.entries(OVERVIEW_COUNTERS)) {
            const value = number(counters[key]);
            const card = element(documentRoot, "article", "ops-counter-card");
            if (value === 0) {
                card.dataset.empty = "true";
            }
            card.append(
                element(documentRoot, "span", null, label),
                element(documentRoot, "strong", null, formatNumber(value)),
            );
            fragment.append(card);
        }
        countersRoot?.replaceChildren(fragment);
    }

    function renderAlerts(alerts = []) {
        if (!alerts.length) {
            renderEmpty(alertsRoot, "Không có cảnh báo đang mở.");
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        for (const alert of alerts) {
            const severity = ["critical", "warning", "info"].includes(String(alert.severity).toLowerCase())
                ? String(alert.severity).toLowerCase()
                : "warning";
            const item = element(documentRoot, "article", "ops-alert");
            item.dataset.severity = severity;
            const content = element(documentRoot, "div", "ops-alert__content");
            content.append(
                element(documentRoot, "span", "ops-severity-label", SEVERITY_LABELS[severity]),
                element(documentRoot, "strong", null, alert.message || alert.code || "Cảnh báo"),
                element(documentRoot, "small", "ops-muted", `Đối tượng cũ nhất: ${formatDateTime(alert.oldest_at || alert.checked_at)}`),
            );
            const actions = element(documentRoot, "div", "ops-alert__actions");
            actions.append(element(documentRoot, "span", "ops-count-badge", formatNumber(alert.count)));
            const link = actionLink(documentRoot, alert.url, alert.action_label || "Kiểm tra");
            if (link) {
                actions.append(link);
            }
            item.append(content, actions);
            fragment.append(item);
        }
        alertsRoot?.replaceChildren(fragment);
    }

    function createLiveMatch(match) {
        const item = element(documentRoot, "article", "ops-live-match");
        if (match.timing_status === "OVERDUE") {
            item.dataset.timing = "overdue";
        }
        const header = element(documentRoot, "div", "ops-live-match__header");
        header.append(
            element(documentRoot, "strong", "ops-room-code", match.room_code || "—"),
            element(
                documentRoot,
                "span",
                "ops-status-label",
                match.timing_status === "OVERDUE" ? "Quá giờ" : (match.status || "Đang chơi"),
            ),
        );
        const players = Array.isArray(match.players) ? match.players : [];
        const versus = players.length
            ? players.map((player) => `${player.username || "—"} ${formatNumber(player.score)}`).join(" — ")
            : "Chưa có dữ liệu người chơi";
        const timing = match.timing_status === "OVERDUE"
            ? `Quá giờ ${formatDuration(match.overdue_seconds)}`
            : `Còn ${formatDuration(match.remaining_seconds)}`;
        const metadata = element(documentRoot, "div", "ops-live-match__meta");
        metadata.append(
            element(documentRoot, "span", null, versus),
            element(documentRoot, "span", null, timing),
            element(documentRoot, "span", null, `${formatNumber(match.pending_submissions)} submission pending`),
        );
        if (number(match.fair_play_flag_count) > 0) {
            metadata.append(element(documentRoot, "span", "ops-fair-play-signal", `${formatNumber(match.fair_play_flag_count)} tín hiệu Fair Play`));
        }
        const link = actionLink(documentRoot, match.url, "Theo dõi");
        item.append(header, metadata);
        if (link) {
            item.append(link);
        }
        return item;
    }

    function renderLiveMatches(matches = [], container, limit) {
        const visibleMatches = matches.slice(0, limit);
        if (!visibleMatches.length) {
            renderEmpty(container, "Hiện không có trận đang diễn ra.");
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        for (const match of visibleMatches) {
            fragment.append(createLiveMatch(match));
        }
        container?.replaceChildren(fragment);
    }

    function renderShortcuts(container, entries) {
        if (!container) {
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        let count = 0;
        for (const [label, item] of entries) {
            const link = actionLink(documentRoot, item?.url, label);
            if (link) {
                fragment.append(link);
                count += 1;
            }
        }
        container.replaceChildren(fragment);
        container.hidden = count === 0;
    }

    function renderSubmissions(data = {}) {
        const summary = element(documentRoot, "dl", "ops-definition-grid");
        appendDefinition(documentRoot, summary, "Tổng lượt nộp", formatNumber(data.total));
        appendDefinition(documentRoot, summary, "Tỷ lệ AC", formatPercent(data.ac_rate));
        appendDefinition(documentRoot, summary, "Pending", formatNumber(data.pending));
        appendDefinition(documentRoot, summary, "Bị treo", formatNumber(data.stale));
        appendDefinition(documentRoot, summary, "Xử lý trung bình", data.average_latency_ms == null ? "—" : `${formatNumber(data.average_latency_ms)} ms`);
        appendDefinition(documentRoot, summary, "p95", data.p95_latency_ms == null ? "—" : `${formatNumber(data.p95_latency_ms)} ms`);

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
                const item = element(documentRoot, "article", "ops-sublist__item");
                item.append(
                    element(documentRoot, "strong", null, `#${error.id}`),
                    element(documentRoot, "span", null, `${error.match_code || "—"} · ${error.player || "—"} · ${error.problem || "—"}`),
                    element(documentRoot, "time", null, formatDateTime(error.received_at)),
                );
                const link = actionLink(documentRoot, error.url, "Mở");
                if (link) {
                    item.append(link);
                }
                errors.append(item);
            }
        }
        submissionsRoot?.replaceChildren(summary, verdicts, errors);
    }

    function renderAIReviews(data = {}) {
        const counts = data.counts || {};
        const summary = element(documentRoot, "dl", "ops-definition-grid");
        for (const status of ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]) {
            appendDefinition(documentRoot, summary, status.charAt(0) + status.slice(1).toLowerCase(), formatNumber(counts[status]));
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
        aiRoot?.replaceChildren(summary, provider, errors);
    }

    function renderFairPlay(data = {}) {
        const players = data.flagged_players || [];
        if (!players.length) {
            renderEmpty(fairPlayRoot, "Không có tín hiệu Fair Play cần xem xét trong 24 giờ.");
            return;
        }
        const fragment = documentRoot.createDocumentFragment();
        for (const player of players) {
            const item = element(documentRoot, "article", "ops-fair-play-row");
            const details = element(documentRoot, "div");
            details.append(
                element(documentRoot, "span", "ops-severity-label", "Cần xem xét"),
                element(documentRoot, "strong", null, `${player.room_code || "—"} · ${player.username || "—"}`),
                element(documentRoot, "span", null, `${player.reason || "Cần xem xét"} · ${formatNumber(player.strike_count)} strike · vắng ${formatDuration(player.away_duration_seconds)} · paste ${formatNumber(player.paste_count)} lần`),
                element(documentRoot, "small", "ops-muted", `Gắn cờ: ${formatDateTime(player.flagged_at)}`),
            );
            const actions = element(documentRoot, "div", "ops-fair-play-row__actions");
            const stateLink = actionLink(documentRoot, player.url, "Xem state");
            const timelineLink = actionLink(documentRoot, player.timeline_url, "Nhật ký");
            if (stateLink) {
                actions.append(stateLink);
            }
            if (timelineLink) {
                actions.append(timelineLink);
            }
            item.append(details, actions);
            fragment.append(item);
        }
        fairPlayRoot?.replaceChildren(fragment);
    }

    function renderKpis(kpis = {}) {
        const fragment = documentRoot.createDocumentFragment();
        for (const [key, label] of Object.entries(KPI_LABELS)) {
            const card = element(documentRoot, "article", "ops-counter-card");
            const value = number(kpis[key]);
            if (value === 0) {
                card.dataset.empty = "true";
            }
            card.append(element(documentRoot, "span", null, label), element(documentRoot, "strong", null, formatNumber(value)));
            fragment.append(card);
        }
        kpisRoot?.replaceChildren(fragment);
    }

    return {
        render(snapshot = {}) {
            const focusedKey = documentRoot.activeElement?.dataset?.opsFocusKey;
            const links = snapshot.links || {};
            renderHealth(snapshot.health || {});
            renderCounters(snapshot.counters || {});
            renderAlerts(snapshot.alerts || []);
            renderLiveMatches(snapshot.live_matches || [], overviewLiveRoot, 5);
            renderLiveMatches(snapshot.live_matches || [], liveRoot, 10);
            overviewLiveLinkRoot?.replaceChildren(actionLink(documentRoot, links.live_matches?.url, "Xem tất cả") || documentRoot.createDocumentFragment());
            renderShortcuts(matchShortcutsRoot, [
                ["Phòng chờ lâu", links.waiting_matches],
                ["Trận quá giờ", links.overdue_matches],
            ]);
            renderShortcuts(queueShortcutsRoot, [
                ["Submission pending", links.pending_submissions],
                ["Tất cả AI Review", links.ai_reviews],
            ]);
            renderShortcuts(systemShortcutsRoot, [
                ["Worker Heartbeats", links.worker_heartbeats],
                ["AI Review", links.ai_reviews],
            ]);
            renderSubmissions(snapshot.submissions || {});
            renderAIReviews(snapshot.ai_reviews || {});
            renderFairPlay(snapshot.fair_play || {});
            renderKpis(snapshot.kpis || {});
            if (focusedKey) {
                const replacement = Array.from(
                    root.querySelectorAll("[data-ops-focus-key]"),
                ).find((item) => item.dataset.opsFocusKey === focusedKey);
                replacement?.focus({preventScroll: true});
            }
        },
        setFresh(value) {
            if (updatedAt) {
                updatedAt.textContent = `Cập nhật: ${formatDateTime(value)}`;
            }
            if (staleNotice) {
                staleNotice.hidden = true;
                staleNotice.textContent = "";
            }
        },
        setStale(message) {
            if (staleNotice) {
                staleNotice.hidden = false;
                staleNotice.textContent = `Dữ liệu có thể đã cũ. ${message}`;
            }
        },
        setRefreshing(isRefreshing) {
            if (refreshButton) {
                refreshButton.disabled = Boolean(isRefreshing);
                refreshButton.textContent = isRefreshing ? "Đang làm mới…" : "Làm mới";
            }
        },
    };
}
