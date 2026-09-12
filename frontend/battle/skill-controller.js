export function createSkillController({
    documentRoot = document,
    api,
    config,
    csrfToken,
    randomUUID,
    refreshState,
    getTypingChallengeId,
    restoreSkillButton,
    combatFeedback,
}) {
    const typingForm = documentRoot.getElementById("typing-form");
    const typingInput = documentRoot.getElementById("typing-input");
    const typingResult = documentRoot.getElementById("typing-result");
    const activeSkills = new Set();
    let typingInFlight = false;

    async function useSkill(skill, button) {
        const skillCode = skill.code;
        if (activeSkills.has(skillCode)) {
            return;
        }
        activeSkills.add(skillCode);
        button.disabled = true;
        try {
            const targetPlayerId = skill.target_mode === "SELF"
                ? config.currentPlayerId
                : config.opponentPlayerId;
            const payload = await api.postJson(
                config.skillUseUrlTemplate.replace("__skill__", skillCode),
                {
                    target_player_id: targetPlayerId,
                    idempotency_key: randomUUID(),
                },
                csrfToken,
            );
            combatFeedback.show(payload.feedback || {
                id: payload.id,
                text: "Kỹ năng đã được kích hoạt",
                cue: "SKILL_USED",
                tone: "SUCCESS",
            });
            await refreshState();
        } catch (error) {
            combatFeedback.showError(error.message);
            restoreSkillButton(button);
        } finally {
            activeSkills.delete(skillCode);
        }
    }

    function bind() {
        typingInput.addEventListener("paste", (event) => {
            event.preventDefault();
            typingResult.textContent = "Hãy tự gõ câu thử thách";
        });

        typingForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const challengeId = getTypingChallengeId();
            if (challengeId === null || typingInFlight) {
                return;
            }
            typingInFlight = true;
            const button = typingForm.querySelector("button[type='submit']");
            button.disabled = true;
            typingResult.textContent = "Đang kiểm tra…";
            try {
                await api.postJson(
                    config.typingCompleteUrlTemplate.replace(
                        "__challenge__",
                        String(challengeId),
                    ),
                    {typed_text: typingInput.value},
                    csrfToken,
                );
                typingResult.textContent = "Đã hoàn thành";
                await refreshState();
            } catch (error) {
                typingResult.textContent = error.message;
            } finally {
                typingInFlight = false;
                button.disabled = false;
            }
        });
    }

    return {bind, useSkill};
}
