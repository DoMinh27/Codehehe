import {createBattleApi} from "../battle/api.js";
import {createReviewController} from "./review-controller.js";
import {createReviewRenderer} from "./review-renderer.js";
import {createRematchController} from "./rematch-controller.js";

export function initializeResult({documentRoot = document, windowObject = window} = {}) {
    const api = createBattleApi({fetchImpl: windowObject.fetch.bind(windowObject)});
    const controllers = [];
    const reviewConfig = documentRoot.getElementById("ai-review-config");
    if (reviewConfig) {
        try {
            const config = JSON.parse(reviewConfig.textContent);
            const controller = createReviewController({
                api, stateUrl: config.stateUrl,
                csrfToken: documentRoot.querySelector("#ai-review-csrf input[name='csrfmiddlewaretoken']")?.value,
                renderer: createReviewRenderer({documentRoot}), documentRoot, windowObject,
            });
            controller.start(config.initialState);
            controllers.push(controller);
        } catch {
            documentRoot.getElementById("ai-review-notice").textContent = "Chưa thể tải phân tích AI. Vui lòng tải lại trang";
        }
    }
    const rematchConfig = documentRoot.getElementById("rematch-config");
    if (rematchConfig) {
        try {
            const config = JSON.parse(rematchConfig.textContent);
            const controller = createRematchController({
                api, stateUrl: config.stateUrl, actionUrl: config.actionUrl,
                csrfToken: documentRoot.querySelector("#rematch-csrf input[name='csrfmiddlewaretoken']")?.value,
                documentRoot, windowObject,
            });
            controller.start(config.initialState);
            controllers.push(controller);
        } catch {
            documentRoot.querySelector("[data-rematch-error]").textContent = "Chưa thể tải tái đấu. Vui lòng tải lại trang";
        }
    }
    return controllers;
}
