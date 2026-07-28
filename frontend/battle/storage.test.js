import {describe, expect, it} from "vitest";

import {
    clearMatchDrafts,
    draftKey,
    loadDraft,
    saveDraft,
} from "./storage.js";


describe("battle draft storage", () => {
    it("isolates, restores, and clears drafts by user and match", () => {
        const storage = window.sessionStorage;
        storage.clear();
        const identity = {userId: 7, matchId: 11, problemId: 13};
        const other = {userId: 8, matchId: 11, problemId: 13};

        saveDraft(storage, identity, "print(1)");
        saveDraft(storage, other, "print(2)");

        expect(loadDraft(storage, identity)).toBe("print(1)");
        expect(storage.getItem(draftKey(other))).toBe("print(2)");

        clearMatchDrafts(storage, identity);
        expect(loadDraft(storage, identity)).toBeNull();
        expect(loadDraft(storage, other)).toBe("print(2)");
    });
});
