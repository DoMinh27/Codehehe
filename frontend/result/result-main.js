import {createBattleApi} from "../battle/api.js";
import {createReviewController} from "./review-controller.js";
import {createReviewRenderer} from "./review-renderer.js";


const configElement = document.getElementById("ai-review-config");
if (!configElement) {
    throw new Error("AI review configuration is missing.");
}

const config = JSON.parse(configElement.textContent);
const api = createBattleApi({fetchImpl: window.fetch.bind(window)});
const renderer = createReviewRenderer({documentRoot: document});
createReviewController({
    api,
    stateUrl: config.stateUrl,
    renderer,
    documentRoot: document,
    windowObject: window,
}).start(config.initialState);
