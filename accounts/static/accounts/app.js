function setupRoomCodeInput() {
    const input = document.querySelector("input[name='room_code']");
    if (!input) {
        return;
    }
    input.addEventListener("input", () => {
        input.value = input.value.replace(/[^a-z0-9]/gi, "").toUpperCase();
    });
}


function setupCopyButtons() {
    for (const button of document.querySelectorAll("[data-copy-target]")) {
        button.addEventListener("click", async () => {
            const target = document.querySelector(button.dataset.copyTarget);
            if (!target) {
                return;
            }
            const originalLabel = button.textContent;
            try {
                await navigator.clipboard.writeText(target.textContent.trim());
                button.textContent = "Đã sao chép";
            } catch {
                button.textContent = "Không thể sao chép";
            }
            window.setTimeout(() => {
                button.textContent = originalLabel;
            }, 1800);
        });
    }
}


setupRoomCodeInput();
setupCopyButtons();
