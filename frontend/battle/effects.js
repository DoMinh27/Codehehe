export function activeEffectCodes(effects, nowMs = Date.now()) {
    return new Set(
        effects
            .filter((effect) => Date.parse(effect.expires_at) > nowMs)
            .map((effect) => effect.code),
    );
}
