import {beforeEach, describe, expect, test, vi} from "vitest";

import {createSkillToolbar} from "./skill-toolbar.js";


const skills = [
    {
        code: "MIRROR_CODE",
        name: "Đảo chiều code",
        description: "Đảo chiều code của đối thủ.",
        energy_cost: 1,
        quantity: 1,
    },
    {
        code: "TYPING_CHALLENGE",
        name: "Thử thách gõ chữ",
        description: "Khóa hành động của đối thủ.",
        energy_cost: 2,
        quantity: 1,
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

    test("uses the icon button itself to activate the skill", () => {
        const trigger = container.querySelector(".skill-trigger");

        trigger.click();

        expect(onUseSkill).toHaveBeenCalledTimes(1);
        expect(onUseSkill).toHaveBeenCalledWith("MIRROR_CODE", trigger);
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
        expect(status.textContent).toBe("Sẵn sàng sử dụng.");
    });

    test.each([
        [
            availableState({energy: 0}),
            "Không đủ năng lượng.",
        ],
        [
            availableState({
                skills: [{...skills[0], quantity: 0}, skills[1]],
            }),
            "Đã hết lượt sử dụng.",
        ],
        [
            availableState({actionLocked: true}),
            "Hành động đang bị khóa bởi Thử thách gõ chữ.",
        ],
        [
            availableState({timedOut: true}),
            "Bạn đã hết thời gian.",
        ],
        [
            availableState({hasOpponent: false}),
            "Chưa có đối thủ để sử dụng skill.",
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
});
