import {createEditors} from "./editor.js";
import {activeEffectCodes, newestSkillUseId} from "./effects.js";
import {clearMatchDrafts} from "./storage.js";


const configElement = document.getElementById("battle-config");
if (!configElement) {
    throw new Error("Battle configuration is missing.");
}

const config = JSON.parse(configElement.textContent);
const identity = {userId: config.userId, matchId: config.matchId};
const editorRegistry = createEditors({
    textareas: document.querySelectorAll(".source-code-input"),
    storage: window.sessionStorage,
    identity,
});
const timer = document.getElementById("match-timer");
const opponentTimer = document.getElementById("opponent-timer");
const problemsContainer = document.getElementById("battle-problems");
const skillList = document.getElementById("skill-list");
const skillNotice = document.getElementById("skill-notice");
const csrfToken = document.querySelector(
    ".submission-form [name='csrfmiddlewaretoken']",
).value;

let remainingSeconds = null;
let opponentRemainingSeconds = null;
let lastStateAt = Date.now();
let finalizeInFlight = false;
let stateInFlight = false;
let pollHandle = null;
let newestRenderedSkillUseId = 0;
let currentState = null;


function formatSeconds(value) {
    const seconds = Math.max(0, value);
    const minutesPart = String(Math.floor(seconds / 60)).padStart(2, "0");
    const secondsPart = String(seconds % 60).padStart(2, "0");
    return `${minutesPart}:${secondsPart}`;
}

function displayedRemaining(serverValue) {
    if (serverValue === null) {
        return null;
    }
    const elapsed = Math.floor((Date.now() - lastStateAt) / 1000);
    return Math.max(0, serverValue - elapsed);
}

function renderTimer() {
    const mine = displayedRemaining(remainingSeconds);
    const theirs = displayedRemaining(opponentRemainingSeconds);
    timer.textContent = mine === null ? "--:--" : formatSeconds(mine);
    opponentTimer.textContent = theirs === null ? "--:--" : formatSeconds(theirs);
    if (mine === 0 && theirs === 0) {
        requestFinalize();
    }
}

function updateProgress(payload) {
    const mySolved = new Set(payload.my_solved_problem_ids);
    const opponentSolved = new Set(payload.opponent_solved_problem_ids);
    for (const tab of document.querySelectorAll(".problem-tab")) {
        const problemId = Number(tab.dataset.matchProblemId);
        tab.querySelector(".my-progress").textContent =
            mySolved.has(problemId) ? "✓ Bạn" : "";
        tab.querySelector(".opponent-progress").textContent =
            opponentSolved.has(problemId) ? "✓ Đối thủ" : "";
        const firstSolver = payload.first_solvers[String(problemId)];
        tab.querySelector(".first-solver").textContent =
            firstSolver === config.currentPlayerId
                ? "★ Bạn giải đầu"
                : firstSolver === config.opponentPlayerId
                    ? "★ Đối thủ giải đầu"
                    : "";
    }
}

function renderSkills(payload, activeCodes) {
    document.getElementById("my-energy").textContent = payload.my_energy;
    skillList.replaceChildren();
    for (const skill of payload.my_skills) {
        const card = document.createElement("article");
        card.className = "skill-card";
        const heading = document.createElement("h3");
        heading.textContent = skill.name;
        const description = document.createElement("p");
        description.textContent = skill.description;
        const resources = document.createElement("p");
        resources.textContent =
            `Charge: ${skill.quantity} — Cost: ${skill.energy_cost} Energy`;
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "Dùng lên đối thủ";
        button.disabled =
            payload.my_timed_out
            || config.opponentPlayerId === null
            || skill.quantity < 1
            || payload.my_energy < skill.energy_cost
            || activeCodes.has(skill.code);
        button.addEventListener("click", () => useSkill(skill.code, button));
        card.append(heading, description, resources, button);
        skillList.append(card);
    }
}

function renderSkillEvents(skillUses) {
    if (!skillUses.length) {
        return;
    }
    const newestId = newestSkillUseId(skillUses);
    const newUses = skillUses.filter(
        (skillUse) => Number(skillUse.id) > newestRenderedSkillUseId,
    );
    if (newUses.length) {
        const latest = newUses.at(-1);
        skillNotice.textContent =
            `${latest.source_username} đã dùng ${latest.name} lên `
            + `${latest.target_username}.`;
    }
    newestRenderedSkillUseId = Math.max(newestRenderedSkillUseId, newestId);
}

function applyEffects(payload) {
    const serverNow = Date.parse(payload.server_time);
    const activeCodes = activeEffectCodes(payload.active_effects, serverNow);
    editorRegistry.setMirrored(activeCodes.has("MIRROR_CODE"));
    problemsContainer.classList.toggle(
        "skill-blur-active",
        activeCodes.has("BLUR_STATEMENT"),
    );
    renderSkills(payload, activeCodes);
}

function updateActionAvailability(payload) {
    for (const form of document.querySelectorAll(".submission-form, .run-form")) {
        const button = form.querySelector("button[type='submit']");
        button.dataset.timedOut = payload.my_timed_out ? "true" : "false";
        button.disabled =
            payload.my_timed_out || button.dataset.inFlight === "true";
    }
}

async function requestFinalize() {
    if (finalizeInFlight) {
        return;
    }
    finalizeInFlight = true;
    try {
        const response = await fetch(config.finalizeUrl, {
            method: "POST",
            headers: {"X-CSRFToken": csrfToken},
        });
        const payload = await response.json();
        if (response.status === 200 && payload.status === "FINISHED") {
            leaveBattle(payload.result_url || config.resultUrl);
        }
    } catch {
        // State polling retries without interrupting the player.
    } finally {
        finalizeInFlight = false;
    }
}

function leaveBattle(url) {
    clearMatchDrafts(window.sessionStorage, identity);
    editorRegistry.destroy();
    window.location.assign(url);
}

async function refreshState() {
    if (stateInFlight) {
        schedulePoll();
        return;
    }
    stateInFlight = true;
    try {
        const response = await fetch(config.stateUrl, {
            headers: {"Accept": "application/json"},
        });
        if (!response.ok) {
            return;
        }
        const payload = await response.json();
        if (payload.status === "FINISHED") {
            leaveBattle(payload.result_url || config.resultUrl);
            return;
        }
        currentState = payload;
        remainingSeconds = payload.remaining_seconds;
        opponentRemainingSeconds = payload.opponent_remaining_seconds;
        lastStateAt = Date.now();
        document.getElementById("my-score").textContent = payload.my_score;
        document.getElementById("opponent-score").textContent =
            payload.opponent_score;
        updateProgress(payload);
        applyEffects(payload);
        updateActionAvailability(payload);
        renderSkillEvents(payload.recent_skill_uses);
        renderTimer();
    } finally {
        stateInFlight = false;
        schedulePoll();
    }
}

function schedulePoll() {
    window.clearTimeout(pollHandle);
    pollHandle = window.setTimeout(
        refreshState,
        document.hidden ? 4000 : 1000,
    );
}

async function useSkill(skillCode, button) {
    button.disabled = true;
    const idempotencyKey = (
        window.crypto && window.crypto.randomUUID
            ? window.crypto.randomUUID()
            : `${Date.now()}-${Math.random()}`
    );
    try {
        const response = await fetch(
            config.skillUseUrlTemplate.replace("__skill__", skillCode),
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    target_player_id: config.opponentPlayerId,
                    idempotency_key: idempotencyKey,
                }),
            },
        );
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "Không thể sử dụng Skill.");
        }
        skillNotice.textContent = "Skill đã được kích hoạt.";
        await refreshState();
    } catch (error) {
        skillNotice.textContent = error.message;
        if (currentState) {
            applyEffects(
                currentState,
            );
        } else {
            button.disabled = false;
        }
    }
}

for (const tab of document.querySelectorAll(".problem-tab")) {
    tab.addEventListener("click", () => {
        for (const problem of document.querySelectorAll(".battle-problem")) {
            problem.hidden = problem.id !== tab.dataset.problemTarget;
        }
    });
}

for (const form of document.querySelectorAll(".submission-form")) {
    const sourceInput = form.querySelector("[name='source_code']");
    sourceInput.addEventListener("input", () => {
        delete form.dataset.idempotencyKey;
    });
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button[type='submit']");
        const result = form.querySelector(".submission-result");
        const idempotencyKey = form.dataset.idempotencyKey || (
            window.crypto && window.crypto.randomUUID
                ? window.crypto.randomUUID()
                : `${Date.now()}-${Math.random()}`
        );
        form.dataset.idempotencyKey = idempotencyKey;
        button.dataset.inFlight = "true";
        button.disabled = true;
        result.textContent = "Đang chấm…";

        try {
            const response = await fetch(form.dataset.submitUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    source_code: sourceInput.value,
                    idempotency_key: idempotencyKey,
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || "Không thể nộp bài.");
            }
            result.textContent = `${payload.verdict}: ${payload.message}`;
            if (payload.verdict !== "PENDING") {
                delete form.dataset.idempotencyKey;
            }
            await refreshState();
        } catch (error) {
            result.textContent = error.message;
        } finally {
            delete button.dataset.inFlight;
            button.disabled = button.dataset.timedOut === "true";
        }
    });
}

for (const form of document.querySelectorAll(".run-form")) {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const problem = form.closest(".battle-problem");
        const button = form.querySelector("button[type='submit']");
        const verdict = form.querySelector(".run-verdict");
        const output = form.querySelector(".run-output");
        const sourceCode = problem.querySelector("[name='source_code']").value;
        const inputData = form.querySelector("[name='input_data']").value;
        button.dataset.inFlight = "true";
        button.disabled = true;
        verdict.textContent = "Đang chạy…";
        output.textContent = "";

        try {
            const response = await fetch(form.dataset.runUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    source_code: sourceCode,
                    input_data: inputData,
                }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || "Không thể chạy code.");
            }
            verdict.textContent = `${payload.verdict}: ${payload.message}`;
            output.textContent = payload.stdout || "(Không có output)";
        } catch (error) {
            verdict.textContent = error.message;
        } finally {
            delete button.dataset.inFlight;
            button.disabled = button.dataset.timedOut === "true";
        }
    });
}

const surrenderForm = document.getElementById("surrender-form");
surrenderForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm("Bạn chắc chắn muốn đầu hàng?")) {
        return;
    }
    const button = surrenderForm.querySelector("button[type='submit']");
    const result = document.getElementById("surrender-result");
    button.disabled = true;
    result.textContent = "Đang kết thúc trận…";
    try {
        const response = await fetch(config.surrenderUrl, {
            method: "POST",
            headers: {"X-CSRFToken": csrfToken},
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "Không thể đầu hàng.");
        }
        leaveBattle(payload.result_url || config.resultUrl);
    } catch (error) {
        result.textContent = error.message;
        button.disabled = false;
    }
});

renderTimer();
window.setInterval(renderTimer, 1000);
refreshState();
document.addEventListener("visibilitychange", schedulePoll);
