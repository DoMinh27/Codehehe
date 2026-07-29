export function draftPrefix({userId, matchId}) {
    return `codehehe:draft:${userId}:${matchId}:`;
}

export function draftKey({userId, matchId, problemId}) {
    return `${draftPrefix({userId, matchId})}${problemId}`;
}

export function loadDraft(storage, identity) {
    try {
        return storage.getItem(draftKey(identity));
    } catch {
        return null;
    }
}

export function saveDraft(storage, identity, sourceCode) {
    try {
        storage.setItem(draftKey(identity), sourceCode);
    } catch {
        // The editor remains usable when storage is unavailable.
    }
}

export function clearMatchDrafts(storage, identity) {
    const prefix = draftPrefix(identity);
    try {
        const keys = [];
        for (let index = 0; index < storage.length; index += 1) {
            const key = storage.key(index);
            if (key && key.startsWith(prefix)) {
                keys.push(key);
            }
        }
        for (const key of keys) {
            storage.removeItem(key);
        }
    } catch {
        // Cleanup is best-effort for restricted browser storage.
    }
}
