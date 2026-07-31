const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const SKILL_ICONS = {
    MIRROR_CODE: "icon-mirror",
    BLUR_STATEMENT: "icon-sparkles",
    TIME_DRAIN_60: "icon-timer",
    TYPING_CHALLENGE: "icon-keyboard",
};


function createIcon(documentRoot, spriteUrl, symbolId) {
    const icon = documentRoot.createElementNS(SVG_NAMESPACE, "svg");
    icon.setAttribute("aria-hidden", "true");
    const use = documentRoot.createElementNS(SVG_NAMESPACE, "use");
    use.setAttribute("href", `${spriteUrl}#${symbolId}`);
    icon.appendChild(use);
    return icon;
}


function unavailableReason({
    actionLocked,
    energy,
    hasOpponent,
    pending,
    skill,
    timedOut,
}) {
    if (pending) {
        return "Đang kích hoạt…";
    }
    if (timedOut) {
        return "Bạn đã hết thời gian.";
    }
    if (actionLocked) {
        return "Hành động đang bị khóa bởi Thử thách gõ chữ.";
    }
    if (!hasOpponent) {
        return "Chưa có đối thủ để sử dụng skill.";
    }
    if (skill.quantity < 1) {
        return "Đã hết lượt sử dụng.";
    }
    if (energy < skill.energy_cost) {
        return "Không đủ năng lượng.";
    }
    return null;
}


export function createSkillToolbar({
    documentRoot = document,
    container,
    iconSpriteUrl = "",
    onUseSkill,
}) {
    const items = new Map();
    const pendingCodes = new Set();
    let latestState = null;

    function renderItem(skill) {
        const item = items.get(skill.code);
        item.skill = skill;
        const reason = unavailableReason({
            ...latestState,
            pending: pendingCodes.has(skill.code),
            skill,
        });
        const isDisabled = reason !== null;

        item.heading.textContent = skill.name;
        item.description.textContent = skill.description;
        item.energy.textContent = `${skill.energy_cost} năng lượng`;
        item.quantity.textContent = String(skill.quantity);
        item.quantityDetail.textContent = `${skill.quantity} lượt còn lại`;
        item.status.textContent = reason || "Sẵn sàng sử dụng.";
        item.status.dataset.available = isDisabled ? "false" : "true";
        item.trigger.disabled = isDisabled;
        item.trigger.setAttribute(
            "aria-label",
            `${skill.name}, ${skill.energy_cost} năng lượng, `
            + `${skill.quantity} lượt còn lại. ${reason || "Sẵn sàng sử dụng."}`,
        );
    }

    async function activateSkill(skillCode) {
        if (pendingCodes.has(skillCode)) {
            return;
        }
        const item = items.get(skillCode);
        pendingCodes.add(skillCode);
        const skill = item.skill;
        renderItem(skill);
        try {
            await onUseSkill(skillCode, item.trigger);
        } finally {
            pendingCodes.delete(skillCode);
            renderItem(item.skill);
        }
    }

    function buildItem(skill) {
        const item = documentRoot.createElement("div");
        item.className = "skill-toolbar__item";
        item.dataset.skillCode = skill.code;

        const trigger = documentRoot.createElement("button");
        trigger.className = "skill-trigger";
        trigger.type = "button";
        trigger.setAttribute("aria-describedby", `skill-tooltip-${skill.code}`);
        trigger.appendChild(createIcon(
            documentRoot,
            iconSpriteUrl,
            SKILL_ICONS[skill.code] || "icon-bolt",
        ));

        const quantity = documentRoot.createElement("span");
        quantity.className = "skill-trigger__quantity";
        quantity.setAttribute("aria-hidden", "true");
        trigger.appendChild(quantity);

        const tooltip = documentRoot.createElement("section");
        tooltip.className = "skill-tooltip";
        tooltip.id = `skill-tooltip-${skill.code}`;
        tooltip.setAttribute("role", "tooltip");

        const heading = documentRoot.createElement("h3");
        const description = documentRoot.createElement("p");
        description.className = "skill-tooltip__description";
        const details = documentRoot.createElement("div");
        details.className = "skill-tooltip__details";
        const energy = documentRoot.createElement("span");
        const quantityDetail = documentRoot.createElement("span");
        details.append(energy, quantityDetail);
        const status = documentRoot.createElement("p");
        status.className = "skill-tooltip__status";
        tooltip.append(heading, description, details, status);

        trigger.addEventListener("click", () => activateSkill(skill.code));
        item.append(trigger, tooltip);
        container.appendChild(item);

        return {
            description,
            energy,
            heading,
            quantity,
            quantityDetail,
            status,
            trigger,
        };
    }

    function ensureItems(skills) {
        const nextCodes = skills.map((skill) => skill.code);
        const currentCodes = [...items.keys()];
        if (
            nextCodes.length === currentCodes.length
            && nextCodes.every((code, index) => code === currentCodes[index])
        ) {
            return;
        }
        container.replaceChildren();
        items.clear();
        for (const skill of skills) {
            items.set(skill.code, buildItem(skill));
        }
    }

    function update({
        skills,
        energy,
        actionLocked,
        timedOut,
        hasOpponent,
    }) {
        latestState = {
            actionLocked,
            energy,
            hasOpponent,
            skills,
            timedOut,
        };
        ensureItems(skills);
        for (const skill of skills) {
            renderItem(skill);
        }
    }

    return {update};
}
