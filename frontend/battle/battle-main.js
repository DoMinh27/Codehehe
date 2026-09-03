import {createBattleApi} from "./api.js";
import {createEditors} from "./editor.js";
import {createIntegrityController} from "./integrity-controller.js";
import {createPolling} from "./polling.js";
import {createSkillController} from "./skill-controller.js";
import {createStateRenderer} from "./state-renderer.js";
import {clearMatchDrafts} from "./storage.js";
import {createSubmissionController} from "./submission-controller.js";


function defaultRandomUUID(windowObject) {
    if (windowObject.crypto?.randomUUID) {
        return windowObject.crypto.randomUUID();
    }
    const bytes = new Uint8Array(16);
    if (windowObject.crypto?.getRandomValues) {
        windowObject.crypto.getRandomValues(bytes);
    } else {
        for (let index = 0; index < bytes.length; index += 1) {
            bytes[index] = Math.floor(Math.random() * 256);
        }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
    return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10).join(""),
    ].join("-");
}


export function bindMobileWorkspaceTabs({documentRoot = document} = {}) {
    for (const paneButton of documentRoot.querySelectorAll(
        "[data-mobile-pane]",
    )) {
        paneButton.addEventListener("click", () => {
            const problem = paneButton.closest(".battle-problem");
            const showEditor = paneButton.dataset.mobilePane === "editor";
            problem.classList.toggle("mobile-show-editor", showEditor);
            for (const button of problem.querySelectorAll(
                "[data-mobile-pane]",
            )) {
                button.setAttribute(
                    "aria-pressed",
                    String(button === paneButton),
                );
            }
        });
    }
}


export function bootstrapBattle({
    documentRoot = document,
    windowObject = window,
    api = createBattleApi({
        fetchImpl: windowObject.fetch.bind(windowObject),
    }),
    randomUUID = () => defaultRandomUUID(windowObject),
} = {}) {
    const configElement = documentRoot.getElementById("battle-config");
    if (!configElement) {
        throw new Error("Battle configuration is missing.");
    }

    const config = JSON.parse(configElement.textContent);
    const identity = {userId: config.userId, matchId: config.matchId};
    const csrfToken = documentRoot.querySelector(
        ".submission-form [name='csrfmiddlewaretoken']",
    ).value;
    const integrityNotice = documentRoot.getElementById("integrity-notice");
    let integrityNoticeHandle = null;
    function showIntegrityNotice(notice) {
        if (!integrityNotice) return;
        windowObject.clearTimeout(integrityNoticeHandle);
        integrityNotice.textContent = notice.message;
        integrityNotice.hidden = false;
        integrityNoticeHandle = windowObject.setTimeout(() => {
            integrityNotice.hidden = true;
        }, 5000);
    }
    const integrityController = config.integrity
        ? createIntegrityController({
            documentRoot,
            windowObject,
            api,
            config,
            csrfToken,
            identity,
            randomUUID,
            onNotice: showIntegrityNotice,
        })
        : null;
    const editorRegistry = createEditors({
        textareas: documentRoot.querySelectorAll(".source-code-input"),
        storage: windowObject.sessionStorage,
        identity,
        onPaste: (characterCount) => (
            integrityController?.recordPaste(characterCount)
        ),
    });
    let finalizeInFlight = false;
    let hasLeftBattle = false;
    let skillController;
    let polling;
    let timerHandle;

    function stop() {
        polling?.stop();
        windowObject.clearInterval(timerHandle);
        windowObject.clearTimeout(integrityNoticeHandle);
        integrityController?.stop();
        documentRoot.removeEventListener(
            "visibilitychange",
            handleVisibilityChange,
        );
    }

    function leaveBattle(url) {
        if (hasLeftBattle) {
            return;
        }
        hasLeftBattle = true;
        stop();
        clearMatchDrafts(windowObject.sessionStorage, identity);
        editorRegistry.destroy();
        windowObject.location.assign(url);
    }

    async function requestFinalize() {
        if (finalizeInFlight || hasLeftBattle) {
            return;
        }
        finalizeInFlight = true;
        try {
            const payload = await api.post(config.finalizeUrl, csrfToken);
            if (payload.status === "FINISHED") {
                leaveBattle(payload.result_url || config.resultUrl);
            }
        } catch {
            // Polling retries while pending submissions are still finishing.
        } finally {
            finalizeInFlight = false;
        }
    }

    const renderer = createStateRenderer({
        documentRoot,
        config,
        editorRegistry,
        onUseSkill: (skill, button) => (
            skillController.useSkill(skill, button)
        ),
        onFinalize: requestFinalize,
    });

    async function refreshState() {
        try {
            const payload = await api.getJson(config.stateUrl);
            if (payload.status === "FINISHED") {
                leaveBattle(payload.result_url || config.resultUrl);
                return;
            }
            renderer.render(payload);
        } catch {
            // A later poll can recover from a temporary network/server error.
        }
    }

    polling = createPolling({
        refresh: refreshState,
        isHidden: () => documentRoot.hidden,
        setTimeoutImpl: windowObject.setTimeout.bind(windowObject),
        clearTimeoutImpl: windowObject.clearTimeout.bind(windowObject),
    });

    skillController = createSkillController({
        documentRoot,
        api,
        config,
        csrfToken,
        randomUUID,
        refreshState: () => polling.refresh(),
        getTypingChallengeId: renderer.getTypingChallengeId,
        restoreSkillButton: renderer.restoreSkillButton,
    });
    skillController.bind();

    createSubmissionController({
        documentRoot,
        api,
        csrfToken,
        randomUUID,
        refreshState: () => polling.refresh(),
    }).bind();

    for (const tab of documentRoot.querySelectorAll(".problem-tab")) {
        tab.addEventListener("click", () => {
            for (const problemTab of documentRoot.querySelectorAll(
                ".problem-tab",
            )) {
                problemTab.setAttribute(
                    "aria-current",
                    problemTab === tab ? "true" : "false",
                );
            }
            for (const problem of documentRoot.querySelectorAll(
                ".battle-problem",
            )) {
                problem.hidden = problem.id !== tab.dataset.problemTarget;
            }
            const typingPanel =
                documentRoot.getElementById("typing-challenge");
            if (!typingPanel.hidden) {
                renderer.moveTypingPopupToVisibleEditor();
            }
        });
    }

    bindMobileWorkspaceTabs({documentRoot});

    const surrenderForm = documentRoot.getElementById("surrender-form");
    surrenderForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!windowObject.confirm("Bạn chắc chắn muốn đầu hàng?")) {
            return;
        }
        const button = surrenderForm.querySelector("button[type='submit']");
        const result = documentRoot.getElementById("surrender-result");
        button.disabled = true;
        result.textContent = "Đang kết thúc trận…";
        try {
            const payload = await api.post(config.surrenderUrl, csrfToken);
            leaveBattle(payload.result_url || config.resultUrl);
        } catch (error) {
            result.textContent = error.message;
            button.disabled = false;
        }
    });

    function handleVisibilityChange() {
        polling.reschedule();
    }

    renderer.renderTimer();
    timerHandle = windowObject.setInterval(renderer.renderTimer, 1000);
    polling.start();
    integrityController?.start();
    documentRoot.addEventListener(
        "visibilitychange",
        handleVisibilityChange,
    );

    return {stop, refreshState};
}
