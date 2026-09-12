const MAX_FEEDBACK_ITEMS = 3;
const FEEDBACK_DURATION_MS = 2800;
const CUE_DURATION_MS = 700;

const CUE_TARGETS = {
    SKILL_USED: ["#skill-list", "combat-cue--skill"],
    SKILL_HIT: [".duel-player--mine", "combat-cue--warning"],
    MIRROR_HIT: [
        ".battle-problem:not([hidden]) .workspace-column",
        "combat-cue--mirror",
    ],
    BLUR_HIT: [
        ".battle-problem:not([hidden]) .problem-content",
        "combat-cue--blur",
    ],
    TIME_DRAIN_HIT: ["#match-timer", "combat-cue--time"],
    TYPING_HIT: ["#typing-challenge", "combat-cue--typing"],
    PURIFY: [".duel-player--mine", "combat-cue--purify"],
    STEAL_GAIN: ["#skill-list", "combat-cue--steal"],
    STEAL_LOSS: ["#skill-list", "combat-cue--warning"],
    SHIELD_READY: [".duel-player--mine", "combat-cue--shield"],
    SHIELD_BLOCK: [".duel-player--mine", "combat-cue--shield"],
    SHIELD_BLOCKED_ATTACK: ["#skill-list", "combat-cue--warning"],
};


export function createCombatFeedback({
    documentRoot = document,
    windowObject = window,
} = {}) {
    const notice = documentRoot.getElementById("skill-notice");
    const queued = [];
    const seenIds = new Set();
    const cueHandles = new Map();
    let initialized = false;
    let active = false;
    let noticeHandle = null;

    function rememberId(value) {
        const id = Number(value);
        if (Number.isFinite(id) && id > 0) {
            seenIds.add(id);
        }
    }

    function playCue(cue) {
        const cueConfig = CUE_TARGETS[cue];
        if (!cueConfig) return;
        const [selector, className] = cueConfig;
        const target = documentRoot.querySelector(selector);
        if (!target) return;

        const previousHandle = cueHandles.get(target);
        windowObject.clearTimeout(previousHandle);
        target.classList.remove("combat-cue", className);
        // Force a style flush so repeating the same cue restarts its animation.
        void target.offsetWidth;
        target.classList.add("combat-cue", className);
        const clearCue = () => {
            windowObject.clearTimeout(cueHandles.get(target));
            target.classList.remove("combat-cue", className);
            target.removeEventListener("animationend", clearCue);
            cueHandles.delete(target);
        };
        target.addEventListener("animationend", clearCue, {once: true});
        cueHandles.set(
            target,
            windowObject.setTimeout(clearCue, CUE_DURATION_MS),
        );
    }

    function showNext() {
        if (active || queued.length === 0 || !notice) return;
        const feedback = queued.shift();
        active = true;
        notice.textContent = feedback.text;
        notice.dataset.tone = feedback.tone || "INFO";
        notice.hidden = false;
        playCue(feedback.cue);
        noticeHandle = windowObject.setTimeout(() => {
            notice.hidden = true;
            notice.textContent = "";
            delete notice.dataset.tone;
            active = false;
            showNext();
        }, FEEDBACK_DURATION_MS);
    }

    function enqueue(feedback) {
        if (!feedback?.text) return;
        if (feedback.id && seenIds.has(Number(feedback.id))) return;
        rememberId(feedback.id);
        while (queued.length >= MAX_FEEDBACK_ITEMS - (active ? 1 : 0)) {
            queued.shift();
        }
        queued.push(feedback);
        showNext();
    }

    function ingest(feedbackItems = []) {
        if (!initialized) {
            for (const feedback of feedbackItems) rememberId(feedback.id);
            initialized = true;
            return;
        }
        for (const feedback of feedbackItems) enqueue(feedback);
    }

    function show(feedback) {
        initialized = true;
        enqueue(feedback);
    }

    function showError(message) {
        show({text: message, cue: "SKILL_HIT", tone: "DANGER"});
    }

    function destroy() {
        windowObject.clearTimeout(noticeHandle);
        queued.length = 0;
        for (const [target, handle] of cueHandles) {
            windowObject.clearTimeout(handle);
            target.classList.remove("combat-cue");
            for (const className of [...target.classList]) {
                if (className.startsWith("combat-cue--")) {
                    target.classList.remove(className);
                }
            }
        }
        cueHandles.clear();
        if (notice) {
            notice.hidden = true;
            notice.textContent = "";
        }
    }

    return {destroy, ingest, show, showError};
}
