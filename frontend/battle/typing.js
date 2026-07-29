export function typingSecondsRemaining(challenge, serverTime) {
    if (!challenge) {
        return 0;
    }
    const expiresAt = Date.parse(challenge.expires_at);
    const serverNow = Date.parse(serverTime);
    if (!Number.isFinite(expiresAt) || !Number.isFinite(serverNow)) {
        return 0;
    }
    return Math.max(0, Math.ceil((expiresAt - serverNow) / 1000));
}

export function typingActionLocked(payload) {
    return Boolean(
        payload.my_action_locked
        && typingSecondsRemaining(
            payload.typing_challenge,
            payload.server_time,
        ) > 0,
    );
}
