export function createSkillController({
    documentRoot = document,
    api,
    config,
    csrfToken,
    randomUUID,
    refreshState,
    getTypingChallengeId,
    restoreSkillButton,
}) {
    const skillNotice = documentRoot.getElementById("skill-notice");
    const typingForm = documentRoot.getElementById("typing-form");
    const typingInput = documentRoot.getElementById("typing-input");
    const typingResult = documentRoot.getElementById("typing-result");
    const activeSkills = new Set();
    let typingInFlight = false;

    function skillNoticeFor(payload) {
        const outcome = payload.outcome || {};
        if (outcome.kind === "PURIFIED_EFFECT") {
            return `Đã thanh tẩy: ${outcome.skill_name}.`;
        }
        if (outcome.kind === "STOLEN_SKILL") {
            return `Đã đánh cắp: ${outcome.skill_name}.`;
        }
        if (outcome.kind === "BLOCKED_BY_SHIELD") {
            return "Skill đã bị Shield của đối thủ chặn.";
        }
        return "Skill đã được kích hoạt.";
    }

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
            skillNotice.textContent = skillNoticeFor(payload);
            await refreshState();
        } catch (error) {
            skillNotice.textContent = error.message;
            restoreSkillButton(button);
        } finally {
            activeSkills.delete(skillCode);
        }
    }

    function bind() {
        typingInput.addEventListener("paste", (event) => {
            event.preventDefault();
            typingResult.textContent = "Hãy tự gõ câu thử thách.";
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
                typingResult.textContent = "Đã hoàn thành.";
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
