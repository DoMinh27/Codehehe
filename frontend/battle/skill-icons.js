const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

export const SKILL_ICONS = {
    MIRROR_CODE: "icon-mirror",
    BLUR_STATEMENT: "icon-sparkles",
    TIME_DRAIN_60: "icon-timer",
    TYPING_CHALLENGE: "icon-keyboard",
    PURIFY: "icon-shield",
    STEAL: "icon-steal",
    SHIELD: "icon-guard",
};


export function createSkillIcon(documentRoot, spriteUrl, skillCode) {
    const icon = documentRoot.createElementNS(SVG_NAMESPACE, "svg");
    icon.setAttribute("aria-hidden", "true");
    const use = documentRoot.createElementNS(SVG_NAMESPACE, "use");
    use.setAttribute(
        "href",
        `${spriteUrl}#${SKILL_ICONS[skillCode] || "icon-bolt"}`,
    );
    icon.appendChild(use);
    return icon;
}
