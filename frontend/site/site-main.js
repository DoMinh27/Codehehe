export function createSiteController({
    documentRoot = document,
    clipboard = navigator.clipboard,
} = {}) {
    function bindDismissibleAlerts() {
        for (const button of documentRoot.querySelectorAll("[data-dismiss-alert]")) {
            button.addEventListener("click", () => button.closest(".alert")?.remove());
        }
    }

    function bindCopyButtons() {
        for (const button of documentRoot.querySelectorAll("[data-copy-target]")) {
            button.addEventListener("click", async () => {
                const target = documentRoot.querySelector(button.dataset.copyTarget);
                const status = button.dataset.copyStatus
                    ? documentRoot.querySelector(button.dataset.copyStatus)
                    : null;
                if (!target) {
                    return;
                }
                try {
                    await clipboard.writeText(target.textContent.trim());
                    if (status) {
                        status.textContent = "Đã sao chép mã phòng.";
                    }
                } catch {
                    if (status) {
                        status.textContent = "Không thể sao chép. Hãy chọn mã phòng thủ công.";
                    }
                }
            });
        }
    }

    return {
        start() {
            bindDismissibleAlerts();
            bindCopyButtons();
        },
    };
}


if (typeof document !== "undefined") {
    createSiteController().start();
}
