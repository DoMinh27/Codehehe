import {afterEach, beforeEach, describe, expect, test, vi} from "vitest";

import {createSkillToolbar} from "./skill-toolbar.js";


const skills = [
    {
        code: "MIRROR_CODE",
        name: "Đảo chiều code",
        description: "Đảo chiều code của đối thủ.",
        energy_cost: 1,
        quantity: 1,
        target_mode: "OPPONENT",
        can_use_while_action_locked: false,
        unavailable_reason: null,
    },
    {
        code: "TYPING_CHALLENGE",
        name: "Thử thách gõ chữ",
        description: "Khóa hành động của đối thủ.",
        energy_cost: 2,
        quantity: 1,
        target_mode: "OPPONENT",
        can_use_while_action_locked: false,
        unavailable_reason: null,
    },
];


function availableState(overrides = {}) {
    return {
        skills,
        energy: 3,
        actionLocked: false,
        timedOut: false,
        hasOpponent: true,
        ...overrides,
    };
}


describe("skill toolbar", () => {
    let container;
    let onUseSkill;
    let toolbar;

    beforeEach(() => {
        document.body.innerHTML = '<div id="skills"></div>';
        container = document.getElementById("skills");
        onUseSkill = vi.fn().mockResolvedValue(undefined);
        toolbar = createSkillToolbar({
            documentRoot: document,
            container,
            iconSpriteUrl: "/static/icons.svg",
            onUseSkill,
        });
        toolbar.update(availableState());
    });

    afterEach(() => {
        toolbar.destroy();
    });

    function setTooltipGeometry({
        trigger = {left: 100, top: 50, width: 36, height: 36},
        tooltip = {width: 288, height: 160},
    } = {}) {
        const triggerElement = container.querySelector(".skill-trigger");
        const tooltipElement = container.querySelector(".skill-tooltip");
        vi.spyOn(triggerElement, "getBoundingClientRect").mockReturnValue({
            ...trigger,
            right: trigger.left + trigger.width,
            bottom: trigger.top + trigger.height,
        });
        vi.spyOn(tooltipElement, "getBoundingClientRect").mockReturnValue({
            ...tooltip,
            right: tooltip.width,
            bottom: tooltip.height,
            left: 0,
            top: 0,
        });
        return {triggerElement, tooltipElement};
    }

    test("renders each skill as an accessible icon button with a rich tooltip", () => {
        const trigger = container.querySelector(".skill-trigger");
        const tooltip = container.querySelector(".skill-tooltip");

        expect(trigger.tagName).toBe("BUTTON");
        expect(trigger.type).toBe("button");
        expect(trigger.textContent).toBe("1");
        expect(trigger.getAttribute("aria-label")).toContain("Đảo chiều code");
        expect(trigger.getAttribute("aria-describedby")).toBe(tooltip.id);
        expect(tooltip.getAttribute("role")).toBe("tooltip");
        expect(tooltip.textContent).toContain("Đảo chiều code");
        expect(tooltip.textContent).toContain("Đảo chiều code của đối thủ.");
        expect(tooltip.textContent).toContain("1 năng lượng");
        expect(tooltip.textContent).toContain("1 lượt còn lại");
        expect(tooltip.textContent).toContain("Sẵn sàng sử dụng");
        expect(tooltip.querySelector("button")).toBeNull();
    });

    test("renders defensive and offensive skills in separate icon-only groups", () => {
        const purify = {
            code: "PURIFY",
            name: "Thanh tẩy",
            description: "Gỡ hiệu ứng.",
            energy_cost: 1,
            quantity: 1,
            target_mode: "SELF",
            can_use_while_action_locked: true,
            ui_group: "DEFENSIVE",
            unavailable_reason: null,
        };
        toolbar.update(availableState({skills: [...skills, purify]}));

        const defensiveGroup = container.querySelector(
            '[data-skill-group="DEFENSIVE"]',
        );
        const offensiveGroup = container.querySelector(
            '[data-skill-group="OFFENSIVE"]',
        );

        expect(defensiveGroup.getAttribute("role")).toBe("group");
        expect(defensiveGroup.getAttribute("aria-label")).toBe("Skill phòng thủ");
        expect(defensiveGroup.querySelectorAll(".skill-trigger")).toHaveLength(1);
        expect(defensiveGroup.querySelector(".skill-toolbar__item").dataset.skillCode).toBe(
            "PURIFY",
        );
        expect(offensiveGroup.getAttribute("aria-label")).toBe("Skill tấn công");
        expect(offensiveGroup.querySelectorAll(".skill-trigger")).toHaveLength(2);
        expect(container.textContent).not.toContain("Phòng thủ");
        expect(container.textContent).not.toContain("Tấn công");
    });

    test("renders Shield as a defensive icon distinct from Purify", () => {
        const shield = {
            code: "SHIELD",
            name: "Shield",
            description: "Chặn skill tấn công tiếp theo.",
            energy_cost: 1,
            quantity: 1,
            target_mode: "SELF",
            can_use_while_action_locked: false,
            ui_group: "DEFENSIVE",
            unavailable_reason: null,
        };

        toolbar.update(availableState({skills: [shield]}));

        const defensiveGroup = container.querySelector(
            '[data-skill-group="DEFENSIVE"]',
        );
        expect(defensiveGroup.querySelector("use").getAttribute("href")).toBe(
            "/static/icons.svg#icon-guard",
        );
        expect(defensiveGroup.querySelector(".skill-tooltip").textContent).toContain(
            "Chặn skill tấn công tiếp theo.",
        );
    });

    test("uses the icon button itself to activate the skill", () => {
        const trigger = container.querySelector(".skill-trigger");

        trigger.click();

        expect(onUseSkill).toHaveBeenCalledTimes(1);
        expect(onUseSkill).toHaveBeenCalledWith(skills[0], trigger);
    });

    test("disables immediately and prevents duplicate requests while activating", async () => {
        let resolveRequest;
        onUseSkill.mockImplementation(() => new Promise((resolve) => {
            resolveRequest = resolve;
        }));
        const trigger = container.querySelector(".skill-trigger");
        const status = container.querySelector(".skill-tooltip__status");

        trigger.click();
        trigger.click();

        expect(trigger.disabled).toBe(true);
        expect(status.textContent).toBe("Đang kích hoạt…");
        expect(onUseSkill).toHaveBeenCalledTimes(1);

        resolveRequest();
        await vi.waitFor(() => expect(trigger.disabled).toBe(false));
        expect(status.textContent).toBe("Sẵn sàng sử dụng");
    });

    test.each([
        [
            availableState({energy: 0}),
            "Không đủ năng lượng",
        ],
        [
            availableState({
                skills: [{...skills[0], quantity: 0}, skills[1]],
            }),
            "Đã hết lượt sử dụng",
        ],
        [
            availableState({actionLocked: true}),
            "Hành động đang bị khóa bởi Thử thách gõ chữ",
        ],
        [
            availableState({timedOut: true}),
            "Bạn đã hết thời gian",
        ],
        [
            availableState({hasOpponent: false}),
            "Chưa có đối thủ để sử dụng skill",
        ],
    ])("disables unavailable skills and explains why", (state, reason) => {
        toolbar.update(state);
        const trigger = container.querySelector(".skill-trigger");
        const status = container.querySelector(".skill-tooltip__status");

        expect(trigger.disabled).toBe(true);
        expect(status.textContent).toBe(reason);
        trigger.click();
        expect(onUseSkill).not.toHaveBeenCalled();
    });

    test("keeps the focused button when polling updates the same skills", () => {
        const trigger = container.querySelector(".skill-trigger");
        trigger.focus();

        toolbar.update(availableState({energy: 2}));

        expect(container.querySelector(".skill-trigger")).toBe(trigger);
        expect(document.activeElement).toBe(trigger);
    });

    test("keeps a focused button when polling moves it to another group", () => {
        const trigger = container.querySelector(".skill-trigger");
        trigger.focus();

        toolbar.update(availableState({
            skills: [{...skills[0], ui_group: "DEFENSIVE"}, skills[1]],
        }));

        expect(container.querySelector('[data-skill-group="DEFENSIVE"] .skill-trigger')).toBe(
            trigger,
        );
        expect(document.activeElement).toBe(trigger);
    });

    test("keeps the active tooltip inside the viewport and clears it after hover", () => {
        Object.defineProperty(window, "innerWidth", {configurable: true, value: 320});
        Object.defineProperty(window, "innerHeight", {configurable: true, value: 640});
        const {triggerElement, tooltipElement} = setTooltipGeometry({
            trigger: {left: 4, top: 50, width: 36, height: 36},
        });
        const item = container.querySelector(".skill-toolbar__item");

        item.dispatchEvent(new Event("mouseenter"));

        expect(item.dataset.tooltipActive).toBe("true");
        expect(tooltipElement.style.left).toBe("12px");
        expect(tooltipElement.style.top).toBe("94px");

        item.dispatchEvent(new Event("mouseleave"));

        expect(item.dataset.tooltipActive).toBeUndefined();
        expect(onUseSkill).not.toHaveBeenCalled();
        expect(triggerElement.disabled).toBe(false);
    });

    test("flips the tooltip above an icon when it cannot fit below", () => {
        Object.defineProperty(window, "innerWidth", {configurable: true, value: 1024});
        Object.defineProperty(window, "innerHeight", {configurable: true, value: 640});
        const {tooltipElement} = setTooltipGeometry({
            trigger: {left: 900, top: 560, width: 36, height: 36},
        });
        const item = container.querySelector(".skill-toolbar__item");

        item.dispatchEvent(new Event("mouseenter"));

        expect(tooltipElement.dataset.placement).toBe("top");
        expect(tooltipElement.style.left).toBe("724px");
        expect(tooltipElement.style.top).toBe("392px");
    });

    test("repositions the active tooltip after scroll and resize", () => {
        Object.defineProperty(window, "innerWidth", {configurable: true, value: 1024});
        Object.defineProperty(window, "innerHeight", {configurable: true, value: 640});
        const {triggerElement, tooltipElement} = setTooltipGeometry();
        const item = container.querySelector(".skill-toolbar__item");

        item.dispatchEvent(new Event("mouseenter"));
        vi.spyOn(triggerElement, "getBoundingClientRect").mockReturnValue({
            left: 700,
            right: 736,
            top: 100,
            bottom: 136,
            width: 36,
            height: 36,
        });
        document.dispatchEvent(new Event("scroll"));

        expect(tooltipElement.style.left).toBe("574px");
        expect(tooltipElement.style.top).toBe("144px");

        vi.spyOn(triggerElement, "getBoundingClientRect").mockReturnValue({
            left: 12,
            right: 48,
            top: 200,
            bottom: 236,
            width: 36,
            height: 36,
        });
        window.dispatchEvent(new Event("resize"));

        expect(tooltipElement.style.left).toBe("12px");
        expect(tooltipElement.style.top).toBe("244px");
    });

    test("shows a disabled skill tooltip from its wrapper without activating it", () => {
        toolbar.update(availableState({energy: 0}));
        const {triggerElement} = setTooltipGeometry();
        const item = container.querySelector(".skill-toolbar__item");

        item.dispatchEvent(new Event("mouseenter"));
        triggerElement.click();

        expect(item.dataset.tooltipActive).toBe("true");
        expect(triggerElement.disabled).toBe(true);
        expect(onUseSkill).not.toHaveBeenCalled();
    });

    test("keeps Purify available during an action lock when an effect exists", () => {
        const purify = {
            code: "PURIFY",
            name: "Thanh tẩy",
            description: "Gỡ hiệu ứng.",
            energy_cost: 1,
            quantity: 1,
            target_mode: "SELF",
            can_use_while_action_locked: true,
            unavailable_reason: null,
        };

        toolbar.update(availableState({skills: [purify], actionLocked: true}));

        const trigger = container.querySelector(".skill-trigger");
        expect(trigger.disabled).toBe(false);
    });

    test("explains when Steal has no eligible target skill", () => {
        const steal = {
            code: "STEAL",
            name: "Steal",
            description: "Cướp skill.",
            energy_cost: 2,
            quantity: 1,
            target_mode: "OPPONENT",
            can_use_while_action_locked: false,
            unavailable_reason: "Đối thủ không còn skill có thể đánh cắp.",
        };

        toolbar.update(availableState({skills: [steal]}));

        expect(container.querySelector(".skill-trigger").disabled).toBe(true);
        expect(container.querySelector(".skill-tooltip__status").textContent).toBe(
            "Đối thủ không còn skill có thể đánh cắp.",
        );
    });
});
