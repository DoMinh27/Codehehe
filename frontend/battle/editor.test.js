import {afterEach, describe, expect, it} from "vitest";

import {createEditors} from "./editor.js";


afterEach(() => {
    document.body.replaceChildren();
    window.sessionStorage.clear();
});

describe("battle editor lock", () => {
    it("locks CodeMirror and the textarea fallback during Typing", () => {
        const textarea = document.createElement("textarea");
        textarea.dataset.matchProblemId = "12";
        textarea.value = "print(1)";
        document.body.append(textarea);

        const editors = createEditors({
            textareas: [textarea],
            storage: window.sessionStorage,
            identity: {userId: 1, matchId: 2},
        });

        editors.setEditable(false);
        expect(textarea.readOnly).toBe(true);
        expect(document.querySelector(".code-editor").dataset.editorLocked).toBe("true");

        editors.setEditable(true);
        expect(textarea.readOnly).toBe(false);
        expect(document.querySelector(".code-editor").dataset.editorLocked).toBe("false");
        editors.destroy();
    });
});
