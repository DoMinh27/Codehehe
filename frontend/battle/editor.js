import {python} from "@codemirror/lang-python";
import {Compartment, EditorState} from "@codemirror/state";
import {EditorView, keymap} from "@codemirror/view";
import {basicSetup} from "codemirror";
import {indentWithTab} from "@codemirror/commands";
import {githubLight} from "@uiw/codemirror-theme-github";

import {loadDraft, saveDraft} from "./storage.js";


export function createEditors({
    textareas,
    storage,
    identity,
    onPaste = () => {},
}) {
    const entries = [];
    const fallbackPasteHandlers = [];

    for (const textarea of textareas) {
        const problemId = Number(textarea.dataset.matchProblemId);
        const draftIdentity = {...identity, problemId};
        const restored = loadDraft(storage, draftIdentity);
        if (restored !== null) {
            textarea.value = restored;
        }

        const mirrorCompartment = new Compartment();
        const editableCompartment = new Compartment();
        const mount = document.createElement("div");
        mount.className = "code-editor";
        textarea.insertAdjacentElement("afterend", mount);
        const handleTextareaPaste = (event) => {
            onPaste(event.clipboardData?.getData("text/plain")?.length || 0);
        };
        textarea.addEventListener("paste", handleTextareaPaste);
        fallbackPasteHandlers.push([textarea, handleTextareaPaste]);

        try {
            const view = new EditorView({
                parent: mount,
                state: EditorState.create({
                    doc: textarea.value,
                    extensions: [
                        basicSetup,
                        python(),
                        githubLight,
                        keymap.of([indentWithTab]),
                        mirrorCompartment.of([]),
                        editableCompartment.of([]),
                        EditorView.updateListener.of((update) => {
                            if (!update.docChanged) {
                                return;
                            }
                            const sourceCode = update.state.doc.toString();
                            textarea.value = sourceCode;
                            textarea.dispatchEvent(
                                new Event("input", {bubbles: true}),
                            );
                            saveDraft(storage, draftIdentity, sourceCode);
                        }),
                        EditorView.domEventHandlers({
                            paste(event) {
                                onPaste(
                                    event.clipboardData
                                        ?.getData("text/plain")
                                        ?.length || 0,
                                );
                                return false;
                            },
                        }),
                    ],
                }),
            });
            textarea.hidden = true;
            entries.push({
                view,
                mirrorCompartment,
                editableCompartment,
                textarea,
                mount,
            });
        } catch {
            mount.remove();
            textarea.hidden = false;
        }
    }

    return {
        setMirrored(active) {
            for (const entry of entries) {
                entry.view.dispatch({
                    effects: entry.mirrorCompartment.reconfigure(
                        active
                            ? [
                                EditorView.contentAttributes.of({dir: "rtl"}),
                                EditorView.theme({
                                    ".cm-content": {
                                        direction: "rtl",
                                        textAlign: "right",
                                    },
                                }),
                            ]
                            : [],
                    ),
                });
            }
        },
        setEditable(editable) {
            for (const entry of entries) {
                entry.textarea.readOnly = !editable;
                entry.mount.dataset.editorLocked = String(!editable);
                entry.view.dispatch({
                    effects: entry.editableCompartment.reconfigure(
                        editable ? [] : [EditorView.editable.of(false)],
                    ),
                });
            }
            for (const textarea of textareas) {
                textarea.readOnly = !editable;
            }
        },
        destroy() {
            for (const entry of entries) {
                entry.view.destroy();
            }
            for (const [textarea, handler] of fallbackPasteHandlers) {
                textarea.removeEventListener("paste", handler);
            }
        },
    };
}
