import {afterEach, beforeEach, describe, expect, it} from "vitest";

import {createDashboardTabs} from "./dashboard-tabs.js";


function setup(hash = "") {
    window.location.hash = hash;
    document.body.innerHTML = `
      <div id="operations-dashboard">
        <div role="tablist">
          <button role="tab" data-dashboard-tab="overview">Tổng quan</button>
          <button role="tab" data-dashboard-tab="matches">Trận đấu</button>
          <button role="tab" data-dashboard-tab="queues">Hàng đợi</button>
        </div>
        <section role="tabpanel" data-dashboard-panel="overview"></section>
        <section role="tabpanel" data-dashboard-panel="matches"></section>
        <section role="tabpanel" data-dashboard-panel="queues"></section>
      </div>
    `;
    const root = document.getElementById("operations-dashboard");
    const tabs = createDashboardTabs({root, documentRoot: document, windowObject: window});
    tabs.start();
    return {root, tabs};
}


beforeEach(() => { document.body.innerHTML = ""; });
afterEach(() => { window.location.hash = ""; });


describe("operations dashboard tabs", () => {
    it("opens the tab selected by a bookmark hash", () => {
        const {root, tabs} = setup("#matches");
        expect(tabs.activeTab).toBe("matches");
        expect(root.querySelector("[data-dashboard-panel='matches']").hidden).toBe(false);
        expect(root.querySelector("[data-dashboard-panel='overview']").hidden).toBe(true);
        tabs.stop();
    });

    it("supports arrow-key navigation without changing any panel content", () => {
        const {root, tabs} = setup();
        const overview = root.querySelector("[data-dashboard-tab='overview']");
        overview.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));

        expect(tabs.activeTab).toBe("matches");
        expect(window.location.hash).toBe("#matches");
        expect(root.querySelector("[data-dashboard-tab='matches']").getAttribute("aria-selected")).toBe("true");
        tabs.stop();
    });
});
