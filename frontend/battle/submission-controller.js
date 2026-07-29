function setButtonAvailable(button) {
    delete button.dataset.inFlight;
    button.disabled =
        button.dataset.timedOut === "true"
        || button.dataset.actionLocked === "true";
}


export function createSubmissionController({
    documentRoot = document,
    api,
    csrfToken,
    randomUUID,
    refreshState,
}) {
    function bindSubmissions() {
        for (const form of documentRoot.querySelectorAll(".submission-form")) {
            const sourceInput = form.querySelector("[name='source_code']");
            sourceInput.addEventListener("input", () => {
                delete form.dataset.idempotencyKey;
            });
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const button = form.querySelector("button[type='submit']");
                if (button.dataset.inFlight === "true") {
                    return;
                }
                const result = form.querySelector(".submission-result");
                const idempotencyKey =
                    form.dataset.idempotencyKey || randomUUID();
                form.dataset.idempotencyKey = idempotencyKey;
                button.dataset.inFlight = "true";
                button.disabled = true;
                result.textContent = "Đang chấm…";

                try {
                    const payload = await api.postJson(
                        form.dataset.submitUrl,
                        {
                            source_code: sourceInput.value,
                            idempotency_key: idempotencyKey,
                        },
                        csrfToken,
                    );
                    result.textContent =
                        `${payload.verdict}: ${payload.message}`;
                    if (payload.verdict !== "PENDING") {
                        delete form.dataset.idempotencyKey;
                    }
                    await refreshState();
                } catch (error) {
                    result.textContent = error.message;
                } finally {
                    setButtonAvailable(button);
                }
            });
        }
    }

    function bindRuns() {
        for (const form of documentRoot.querySelectorAll(".run-form")) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const problem = form.closest(".battle-problem");
                const button = form.querySelector("button[type='submit']");
                if (button.dataset.inFlight === "true") {
                    return;
                }
                const verdict = form.querySelector(".run-verdict");
                const output = form.querySelector(".run-output");
                button.dataset.inFlight = "true";
                button.disabled = true;
                verdict.textContent = "Đang chạy…";
                output.textContent = "";

                try {
                    const payload = await api.postJson(
                        form.dataset.runUrl,
                        {
                            source_code: problem.querySelector(
                                "[name='source_code']",
                            ).value,
                            input_data: form.querySelector(
                                "[name='input_data']",
                            ).value,
                        },
                        csrfToken,
                    );
                    verdict.textContent =
                        `${payload.verdict}: ${payload.message}`;
                    output.textContent = payload.stdout || "(Không có output)";
                } catch (error) {
                    verdict.textContent = error.message;
                } finally {
                    setButtonAvailable(button);
                }
            });
        }
    }

    return {
        bind() {
            bindSubmissions();
            bindRuns();
        },
    };
}
