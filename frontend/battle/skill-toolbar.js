const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const SKILL_ICONS = {
    MIRROR_CODE: "icon-mirror",
    BLUR_STATEMENT: "icon-sparkles",
    TIME_DRAIN_60: "icon-timer",
    TYPING_CHALLENGE: "icon-keyboard",
    PURIFY: "icon-shield",
    STEAL: "icon-steal",
    SHIELD: "icon-guard",
};
const DEFENSIVE_GROUP = "DEFENSIVE";
const OFFENSIVE_GROUP = "OFFENSIVE";
const SKILL_GROUPS = [
    [DEFENSIVE_GROUP, "Skill phòng thủ"],
    [OFFENSIVE_GROUP, "Skill tấn công"],
];


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
        return "Bạn đã hết thời gian";
    }
    if (actionLocked && !skill.can_use_while_action_locked) {
        return "Hành động đang bị khóa bởi Thử thách gõ chữ";
    }
    if (skill.target_mode === "OPPONENT" && !hasOpponent) {
        return "Chưa có đối thủ để sử dụng skill";
    }
    if (skill.quantity < 1) {
        return "Đã hết lượt sử dụng";
    }
    if (energy < skill.energy_cost) {
        return "Không đủ năng lượng";
    }
    return skill.unavailable_reason || null;
}


export function createSkillToolbar({
    documentRoot = document,
    container,
    iconSpriteUrl = "",
    onUseSkill,
}) {
    const items = new Map();
    const pendingCodes = new Set();
    const groupContainers = new Map();
    const windowRoot = documentRoot.defaultView;
    let latestState = null;
    let activeItem = null;

    function skillGroup(skill) {
        return skill.ui_group === DEFENSIVE_GROUP
            ? DEFENSIVE_GROUP
            : OFFENSIVE_GROUP;
    }

    function ensureGroups() {
        for (const [group, label] of SKILL_GROUPS) {
            let groupContainer = container.querySelector(
                `[data-skill-group="${group}"]`,
            );
            if (!groupContainer) {
                groupContainer = documentRoot.createElement("div");
                groupContainer.className = "skill-toolbar__group";
                if (group === OFFENSIVE_GROUP) {
                    groupContainer.classList.add("skill-toolbar__group--offensive");
                }
                groupContainer.dataset.skillGroup = group;
                groupContainer.setAttribute("role", "group");
                groupContainer.setAttribute("aria-label", label);
                container.appendChild(groupContainer);
            }
            groupContainers.set(group, groupContainer);
        }
    }

    function clamp(value, minimum, maximum) {
        return Math.min(Math.max(value, minimum), maximum);
    }

    function positionTooltip(item) {
        if (!windowRoot || activeItem !== item || !item?.element.isConnected) {
            if (activeItem === item) {
                deactivateTooltip(item);
            }
            return;
        }

        const viewportMargin = 12;
        const tooltipGap = 8;
        const triggerRect = item.trigger.getBoundingClientRect();
        const tooltipRect = item.tooltip.getBoundingClientRect();
        const viewportWidth = windowRoot.innerWidth;
        const viewportHeight = windowRoot.innerHeight;
        const tooltipWidth = Math.min(
            tooltipRect.width || 288,
            Math.max(0, viewportWidth - (viewportMargin * 2)),
        );
        const tooltipHeight = tooltipRect.height || 160;
        const preferredTop = triggerRect.bottom + tooltipGap;
        const flippedTop = triggerRect.top - tooltipGap - tooltipHeight;
        const fitsBelow = preferredTop + tooltipHeight <= viewportHeight - viewportMargin;
        const fitsAbove = flippedTop >= viewportMargin;
        const left = clamp(
            triggerRect.left + (triggerRect.width / 2) - (tooltipWidth / 2),
            viewportMargin,
            Math.max(viewportMargin, viewportWidth - viewportMargin - tooltipWidth),
        );
        const top = fitsBelow
            ? preferredTop
            : fitsAbove
                ? flippedTop
                : clamp(
                    preferredTop,
                    viewportMargin,
                    Math.max(viewportMargin, viewportHeight - viewportMargin - tooltipHeight),
                );

        item.tooltip.dataset.placement = fitsBelow ? "bottom" : "top";
        item.tooltip.style.left = `${Math.round(left)}px`;
        item.tooltip.style.top = `${Math.round(top)}px`;
    }

    function deactivateTooltip(item = activeItem) {
        if (!item) {
            return;
        }
        item.element.removeAttribute("data-tooltip-active");
        if (activeItem === item) {
            activeItem = null;
        }
    }

    function activateTooltip(item) {
        if (activeItem && activeItem !== item) {
            deactivateTooltip(activeItem);
        }
        activeItem = item;
        item.element.dataset.tooltipActive = "true";
        positionTooltip(item);
    }

    function refreshActiveTooltip() {
        positionTooltip(activeItem);
    }

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
        item.status.textContent = reason || "Sẵn sàng sử dụng";
        item.status.dataset.available = isDisabled ? "false" : "true";
        item.trigger.disabled = isDisabled;
        item.trigger.setAttribute(
            "aria-label",
            `${skill.name}, ${skill.energy_cost} năng lượng, `
            + `${skill.quantity} lượt còn lại. ${reason || "Sẵn sàng sử dụng"}`,
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
            await onUseSkill(skill, item.trigger);
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
        item.addEventListener("mouseenter", () => activateTooltip(itemState));
        item.addEventListener("mouseleave", () => {
            if (!item.contains(documentRoot.activeElement)) {
                deactivateTooltip(itemState);
            }
        });
        trigger.addEventListener("focus", () => activateTooltip(itemState));
        trigger.addEventListener("blur", () => {
            windowRoot?.setTimeout(() => {
                if (!item.contains(documentRoot.activeElement)) {
                    deactivateTooltip(itemState);
                }
            });
        });
        item.append(trigger, tooltip);

        const itemState = {
            description,
            element: item,
            energy,
            heading,
            quantity,
            quantityDetail,
            status,
            trigger,
            tooltip,
        };
        return itemState;
    }

    function ensureItems(skills) {
        const nextCodes = new Set(skills.map((skill) => skill.code));
        for (const [code, item] of items) {
            if (!nextCodes.has(code)) {
                deactivateTooltip(item);
                item.element.remove();
                items.delete(code);
            }
        }
        for (const skill of skills) {
            let item = items.get(skill.code);
            if (!item) {
                item = buildItem(skill);
                items.set(skill.code, item);
            }
            const groupContainer = groupContainers.get(skillGroup(skill));
            if (item.element.parentElement !== groupContainer) {
                const hadFocus = documentRoot.activeElement === item.trigger;
                groupContainer.appendChild(item.element);
                if (hadFocus) {
                    item.trigger.focus({preventScroll: true});
                }
            }
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

    documentRoot.addEventListener("scroll", refreshActiveTooltip, true);
    windowRoot?.addEventListener("resize", refreshActiveTooltip);
    ensureGroups();

    return {
        update,
        destroy() {
            deactivateTooltip();
            documentRoot.removeEventListener("scroll", refreshActiveTooltip, true);
            windowRoot?.removeEventListener("resize", refreshActiveTooltip);
        },
    };
}
