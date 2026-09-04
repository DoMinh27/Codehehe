function tabFromHash(hash) {
    return String(hash || "").replace(/^#/, "");
}


export function createDashboardTabs({root, documentRoot = document, windowObject = window}) {
    const tabs = Array.from(root?.querySelectorAll("[role='tab'][data-dashboard-tab]") || []);
    const panels = Array.from(root?.querySelectorAll("[role='tabpanel'][data-dashboard-panel]") || []);
    let activeTab = null;

    function select(tabName, {focus = false, updateHash = false} = {}) {
        const nextTab = tabs.find((tab) => tab.dataset.dashboardTab === tabName) || tabs[0];
        if (!nextTab) {
            return;
        }
        activeTab = nextTab.dataset.dashboardTab;
        for (const tab of tabs) {
            const selected = tab === nextTab;
            tab.setAttribute("aria-selected", String(selected));
            tab.tabIndex = selected ? 0 : -1;
        }
        for (const panel of panels) {
            panel.hidden = panel.dataset.dashboardPanel !== activeTab;
        }
        if (focus) {
            nextTab.focus();
        }
        if (updateHash && windowObject.location.hash !== `#${activeTab}`) {
            windowObject.location.hash = activeTab;
        }
    }

    function handleClick(event) {
        const tab = event.currentTarget;
        select(tab.dataset.dashboardTab, {updateHash: true});
    }

    function handleKeydown(event) {
        const currentIndex = tabs.indexOf(event.currentTarget);
        if (currentIndex === -1) {
            return;
        }
        let nextIndex = null;
        if (event.key === "ArrowRight") {
            nextIndex = (currentIndex + 1) % tabs.length;
        } else if (event.key === "ArrowLeft") {
            nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        } else if (event.key === "Home") {
            nextIndex = 0;
        } else if (event.key === "End") {
            nextIndex = tabs.length - 1;
        }
        if (nextIndex === null) {
            return;
        }
        event.preventDefault();
        select(tabs[nextIndex].dataset.dashboardTab, {focus: true, updateHash: true});
    }

    function handleHashChange() {
        select(tabFromHash(windowObject.location.hash));
    }

    return {
        start() {
            for (const tab of tabs) {
                tab.addEventListener("click", handleClick);
                tab.addEventListener("keydown", handleKeydown);
            }
            windowObject.addEventListener("hashchange", handleHashChange);
            select(tabFromHash(windowObject.location.hash));
        },
        stop() {
            for (const tab of tabs) {
                tab.removeEventListener("click", handleClick);
                tab.removeEventListener("keydown", handleKeydown);
            }
            windowObject.removeEventListener("hashchange", handleHashChange);
        },
        get activeTab() {
            return activeTab;
        },
    };
}


export function createDashboardSidebarToggle({root, documentRoot = document}) {
    const button = root?.querySelector("#ops-sidebar-toggle");
    const body = documentRoot.body;
    const className = "ops-admin-sidebar-open";

    function render() {
        const expanded = body?.classList.contains(className);
        if (button) {
            button.setAttribute("aria-expanded", String(expanded));
            button.textContent = expanded ? "Ẩn menu quản trị" : "Mở menu quản trị";
        }
    }

    function toggle() {
        body?.classList.toggle(className);
        render();
    }

    return {
        start() {
            body?.classList.remove(className);
            button?.addEventListener("click", toggle);
            render();
        },
        stop() {
            button?.removeEventListener("click", toggle);
            body?.classList.remove(className);
        },
    };
}
