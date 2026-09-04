import {createDashboardController} from "./dashboard-controller.js";
import {createDashboardRenderer} from "./dashboard-renderer.js";
import {createDashboardSidebarToggle, createDashboardTabs} from "./dashboard-tabs.js";


export function startOperationsDashboard({documentRoot = document, windowObject = window} = {}) {
    const root = documentRoot.getElementById("operations-dashboard");
    const initialStateElement = documentRoot.getElementById("operations-dashboard-initial-state");
    if (!root || !initialStateElement) {
        return null;
    }
    let initialState = {};
    try {
        initialState = JSON.parse(initialStateElement.textContent);
    } catch (_error) {
        initialState = {};
    }
    const renderer = createDashboardRenderer({root, documentRoot});
    const tabs = createDashboardTabs({root, documentRoot, windowObject});
    const sidebarToggle = createDashboardSidebarToggle({root, documentRoot});
    const controller = createDashboardController({
        root,
        renderer,
        documentRoot,
        windowObject,
        fetchImpl: windowObject.fetch.bind(windowObject),
    });
    tabs.start();
    sidebarToggle.start();
    controller.start(initialState);
    return {
        ...controller,
        stop() {
            controller.stop();
            tabs.stop();
            sidebarToggle.stop();
        },
    };
}


if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => startOperationsDashboard());
}

