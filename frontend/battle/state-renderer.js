import {activeEffectCodes} from "./effects.js";
import {createSkillIcon} from "./skill-icons.js";
import {createSkillToolbar} from "./skill-toolbar.js";
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
    combatFeedback,
    onUseSkill,
    onFinalize,
}) {
    const timer = documentRoot.getElementById("match-timer");
    const opponentTimer = documentRoot.getElementById("opponent-timer");
    const problemsContainer = documentRoot.getElementById("battle-problems");
    const skillList = documentRoot.getElementById("skill-list");
    const activeEffectsContainer = documentRoot.getElementById(
        "my-active-effects",
    );
    const typingPanel = documentRoot.getElementById("typing-challenge");
    const typingPrompt = documentRoot.getElementById("typing-prompt");
    const typingCountdown = documentRoot.getElementById("typing-countdown");
    const typingInput = documentRoot.getElementById("typing-input");
    const typingResult = documentRoot.getElementById("typing-result");
    const skillToolbar = createSkillToolbar({
        documentRoot,
        container: skillList,
        iconSpriteUrl: skillList.dataset.iconSpriteUrl,
        onUseSkill,
    });

    let remainingSeconds = null;
    let opponentRemainingSeconds = null;
    let typingRemainingSeconds = 0;
    let lastStateAt = now();
    let activeEffectClockOffset = 0;
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
            tab.querySelector(".my-progress").textContent = (
                mySolved.has(problemId) ? "✓ Bạn" : ""
            );
            tab.querySelector(".opponent-progress").textContent = (
                opponentSolved.has(problemId) ? "✓ Đối thủ" : ""
            );
            const firstSolver = payload.first_solvers[String(problemId)];
            tab.querySelector(".first-solver").textContent = (
                firstSolver === config.currentPlayerId
                    ? "★ Bạn giải đầu"
                    : firstSolver === config.opponentPlayerId
                        ? "★ Đối thủ giải đầu"
                        : ""
            );
        }
    }

    function renderSkills(payload) {
        documentRoot.getElementById("my-energy").textContent = payload.my_energy;
        skillToolbar.update({
            skills: payload.my_skills,
            energy: payload.my_energy,
            actionLocked: payload.my_action_locked,
            timedOut: payload.my_timed_out,
            hasOpponent: config.opponentPlayerId !== null,
        });
    }

    function moveTypingPopupToVisibleEditor() {
        const visibleProblem = [...problemsContainer.querySelectorAll(
            ".battle-problem",
        )].find((problem) => !problem.hidden);
        const submissionForm = visibleProblem?.querySelector(".submission-form");
        const workspace = submissionForm?.parentElement;
        if (
            submissionForm
            && (
                typingPanel.parentElement !== workspace
                || typingPanel.nextElementSibling !== submissionForm
            )
        ) {
            workspace.insertBefore(typingPanel, submissionForm);
        }
        visibleProblem.classList.add("mobile-show-editor");
        for (const button of visibleProblem.querySelectorAll(
            "[data-mobile-pane]",
        )) {
            button.setAttribute(
                "aria-pressed",
                String(button.dataset.mobilePane === "editor"),
            );
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

    function activeEffectSeconds(effect) {
        const serverNow = now() + activeEffectClockOffset;
        return Math.max(
            0,
            Math.ceil((Date.parse(effect.expires_at) - serverNow) / 1000),
        );
    }

    function renderActiveEffects() {
        if (!activeEffectsContainer || !currentState) return;
        const effects = currentState.active_effects.filter(
            (effect) => activeEffectSeconds(effect) > 0,
        );
        activeEffectsContainer.replaceChildren();
        activeEffectsContainer.hidden = effects.length === 0;
        for (const effect of effects) {
            const seconds = activeEffectSeconds(effect);
            const chip = documentRoot.createElement("span");
            chip.className = "active-effect-chip";
            chip.dataset.effectCode = effect.code;
            chip.setAttribute(
                "aria-label",
                `${effect.name} còn ${seconds} giây`,
            );
            chip.appendChild(createSkillIcon(
                documentRoot,
                skillList.dataset.iconSpriteUrl,
                effect.code,
            ));
            const label = documentRoot.createElement("span");
            label.textContent = `${effect.name} ${seconds}s`;
            chip.appendChild(label);
            activeEffectsContainer.appendChild(chip);
        }
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
        renderSkills(payload);
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
            button.disabled = (
                payload.my_timed_out
                || payload.my_action_locked
                || button.dataset.inFlight === "true"
            );
        }
    }

    function renderTimer() {
        const mine = displayedRemaining(remainingSeconds);
        const theirs = displayedRemaining(opponentRemainingSeconds);
        timer.textContent = mine === null ? "--:--" : formatSeconds(mine);
        opponentTimer.textContent = (
            theirs === null ? "--:--" : formatSeconds(theirs)
        );
        const typingRemaining = displayedRemaining(typingRemainingSeconds);
        typingCountdown.textContent = String(typingRemaining ?? 0);
        renderActiveEffects();
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
        activeEffectClockOffset = Date.parse(payload.server_time) - now();
        documentRoot.getElementById("my-score").textContent = payload.my_score;
        documentRoot.getElementById("opponent-score").textContent = (
            payload.opponent_score
        );
        updateProgress(payload);
        renderTypingChallenge(payload);
        applyEffects(payload);
        updateActionAvailability(payload);
        combatFeedback.ingest(payload.combat_notifications || []);
        renderTimer();
    }

    return {
        render,
        renderTimer,
        moveTypingPopupToVisibleEditor,
        getTypingChallengeId: () => typingChallengeId,
        getCurrentState: () => currentState,
        destroy() {
            skillToolbar.destroy();
        },
        restoreSkillButton(button) {
            if (currentState) {
                applyEffects(currentState);
            } else {
                button.disabled = false;
            }
        },
    };
}
