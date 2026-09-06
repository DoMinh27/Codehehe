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
                        status.textContent = "Đã sao chép mã phòng";
                    }
                } catch {
                    if (status) {
                        status.textContent = "Không thể sao chép. Hãy chọn mã phòng thủ công";
                    }
                }
            });
        }
    }

    function fieldIsLocallyValid(field) {
        if (!field.checkValidity()) {
            return false;
        }
        const minimumLength = Number(field.getAttribute("minlength") || 0);
        if (minimumLength && field.value.length < minimumLength) {
            return false;
        }
        const matchId = field.dataset.authMatch;
        if (!matchId) {
            return true;
        }
        return field.value === documentRoot.getElementById(matchId)?.value;
    }

    function clearFieldError(field) {
        if (!fieldIsLocallyValid(field)) {
            return;
        }
        const fieldContainer = field.closest(".form-field");
        const error = fieldContainer?.querySelector("[data-auth-field-error]");
        if (!error) {
            return;
        }
        const errorId = error.id;
        error.remove();
        fieldContainer.classList.remove("form-field--error");
        field.removeAttribute("aria-invalid");
        const describedBy = (field.getAttribute("aria-describedby") || "")
            .split(/\s+/)
            .filter((id) => id && id !== errorId);
        if (describedBy.length) {
            field.setAttribute("aria-describedby", describedBy.join(" "));
        } else {
            field.removeAttribute("aria-describedby");
        }
    }

    function bindAuthForms() {
        let focusTarget = null;
        for (const form of documentRoot.querySelectorAll("[data-auth-form]")) {
            const banner = form.querySelector("[data-auth-form-alert]");
            focusTarget ||= banner || form.querySelector('[aria-invalid="true"]');
            for (const field of form.querySelectorAll("[data-auth-input]")) {
                field.addEventListener("input", () => {
                    if (banner) {
                        banner.hidden = true;
                    }
                    clearFieldError(field);
                });
            }
        }
        focusTarget?.focus();
    }

    return {
        start() {
            bindDismissibleAlerts();
            bindCopyButtons();
            bindAuthForms();
        },
    };
}


if (typeof document !== "undefined") {
    createSiteController().start();
}
