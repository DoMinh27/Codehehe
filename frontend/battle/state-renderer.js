import {activeEffectCodes, newestSkillUseId} from "./effects.js";
import {typingActionLocked, typingSecondsRemaining} from "./typing.js";


export function formatSeconds(value) {
    const seconds = Math.max(0, value);
    const minutesPart = String(Math.floor(seconds / 60)).padStart(2, "0");
    const secondsPart = String(seconds % 60).padStart(2, "0");
    return `${minutesPart}:${secondsPart}`;
}


export function createStateRenderer({
    documentRoot = document,
    now = () => Date.now(),
    config,
    editorRegistry,
    onUseSkill,
    onFinalize,
}) {
    const timer = documentRoot.getElementById("match-timer");
    const opponentTimer = documentRoot.getElementById("opponent-timer");
    const problemsContainer = documentRoot.getElementById("battle-problems");
    const skillList = documentRoot.getElementById("skill-list");
    const skillNotice = documentRoot.getElementById("skill-notice");
    const typingPanel = documentRoot.getElementById("typing-challenge");
    const typingPrompt = documentRoot.getElementById("typing-prompt");
    const typingCountdown = documentRoot.getElementById("typing-countdown");
    const typingInput = documentRoot.getElementById("typing-input");
    const typingResult = documentRoot.getElementById("typing-result");

    let remainingSeconds = null;
    let opponentRemainingSeconds = null;
    let typingRemainingSeconds = 0;
    let lastStateAt = now();
    let newestRenderedSkillUseId = 0;
    let currentState = null;
    let typingChallengeId = null;

    function displayedRemaining(serverValue) {
        if (serverValue === null) {
            return null;
        }
        const elapsed = Math.floor((now() - lastStateAt) / 1000);
        return Math.max(0, serverValue - elapsed);
    }

    function updateProgress(payload) {
        const mySolved = new Set(payload.my_solved_problem_ids);
        const opponentSolved = new Set(payload.opponent_solved_problem_ids);
        for (const tab of documentRoot.querySelectorAll(".problem-tab")) {
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
        documentRoot.getElementById("my-energy").textContent = payload.my_energy;
        skillList.replaceChildren();
        for (const skill of payload.my_skills) {
            const card = documentRoot.createElement("article");
            card.className = "skill-card";
            const heading = documentRoot.createElement("h3");
            heading.textContent = skill.name;
            const description = documentRoot.createElement("p");
            description.textContent = skill.description;
            const resources = documentRoot.createElement("p");
            resources.textContent =
                `Còn ${skill.quantity} lượt · Tốn ${skill.energy_cost} energy`;
            const button = documentRoot.createElement("button");
            button.type = "button";
            button.textContent = "Kích hoạt";
            button.disabled =
                payload.my_timed_out
                || payload.my_action_locked
                || config.opponentPlayerId === null
                || skill.quantity < 1
                || payload.my_energy < skill.energy_cost
                || activeCodes.has(skill.code);
            button.addEventListener(
                "click",
                () => onUseSkill(skill.code, button),
            );
            card.append(heading, description, resources, button);
            skillList.append(card);
        }
    }

    function moveTypingPopupToVisibleEditor() {
        const visibleProblem = [...problemsContainer.querySelectorAll(
            ".battle-problem",
        )].find((problem) => !problem.hidden);
        const submissionForm = visibleProblem?.querySelector(".submission-form");
        if (
            submissionForm
            && (
                typingPanel.parentElement !== visibleProblem
                || typingPanel.nextElementSibling !== submissionForm
            )
        ) {
            visibleProblem.insertBefore(typingPanel, submissionForm);
        }
    }

    function renderTypingChallenge(payload) {
        const challenge = payload.typing_challenge;
        const isLocked = typingActionLocked(payload);
        typingRemainingSeconds = typingSecondsRemaining(
            challenge,
            payload.server_time,
        );
        if (!isLocked || !challenge) {
            typingPanel.hidden = true;
            typingChallengeId = null;
            editorRegistry.setEditable(true);
            return;
        }
        if (typingChallengeId !== challenge.id) {
            typingInput.value = "";
            typingResult.textContent = "";
        }
        typingChallengeId = challenge.id;
        typingPrompt.textContent = challenge.prompt;
        moveTypingPopupToVisibleEditor();
        typingPanel.hidden = false;
        editorRegistry.setEditable(false);
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
        newestRenderedSkillUseId = Math.max(
            newestRenderedSkillUseId,
            newestId,
        );
    }

    function applyEffects(payload) {
        const serverNow = Date.parse(payload.server_time);
        const activeCodes = activeEffectCodes(
            payload.active_effects,
            serverNow,
        );
        editorRegistry.setMirrored(activeCodes.has("MIRROR_CODE"));
        problemsContainer.classList.toggle(
            "skill-blur-active",
            activeCodes.has("BLUR_STATEMENT"),
        );
        renderSkills(payload, activeCodes);
    }

    function updateActionAvailability(payload) {
        for (const form of documentRoot.querySelectorAll(
            ".submission-form, .run-form",
        )) {
            const button = form.querySelector("button[type='submit']");
            button.dataset.timedOut = payload.my_timed_out ? "true" : "false";
            button.dataset.actionLocked = (
                payload.my_action_locked ? "true" : "false"
            );
            button.disabled =
                payload.my_timed_out
                || payload.my_action_locked
                || button.dataset.inFlight === "true";
        }
    }

    function renderTimer() {
        const mine = displayedRemaining(remainingSeconds);
        const theirs = displayedRemaining(opponentRemainingSeconds);
        timer.textContent = mine === null ? "--:--" : formatSeconds(mine);
        opponentTimer.textContent =
            theirs === null ? "--:--" : formatSeconds(theirs);
        const typingRemaining = displayedRemaining(typingRemainingSeconds);
        typingCountdown.textContent = String(typingRemaining ?? 0);
        if (
            typingChallengeId !== null
            && typingRemaining === 0
            && currentState
        ) {
            typingPanel.hidden = true;
            typingChallengeId = null;
            currentState.my_action_locked = false;
            currentState.typing_challenge = null;
            editorRegistry.setEditable(true);
            applyEffects(currentState);
            updateActionAvailability(currentState);
        }
        if (mine === 0 && theirs === 0) {
            onFinalize();
        }
    }

    function render(payload) {
        currentState = payload;
        payload.my_action_locked = typingActionLocked(payload);
        remainingSeconds = payload.remaining_seconds;
        opponentRemainingSeconds = payload.opponent_remaining_seconds;
        lastStateAt = now();
        documentRoot.getElementById("my-score").textContent = payload.my_score;
        documentRoot.getElementById("opponent-score").textContent =
            payload.opponent_score;
        updateProgress(payload);
        renderTypingChallenge(payload);
        applyEffects(payload);
        updateActionAvailability(payload);
        renderSkillEvents(payload.recent_skill_uses);
        renderTimer();
    }

    return {
        render,
        renderTimer,
        moveTypingPopupToVisibleEditor,
        getTypingChallengeId: () => typingChallengeId,
        getCurrentState: () => currentState,
        restoreSkillButton(button) {
            if (currentState) {
                applyEffects(currentState);
            } else {
                button.disabled = false;
            }
        },
    };
}
