export function activeEffectCodes(effects, nowMs = Date.now()) {
    return new Set(
        effects
            .filter((effect) => Date.parse(effect.expires_at) > nowMs)
            .map((effect) => effect.code),
    );
}

export function newestSkillUseId(skillUses) {
    return skillUses.reduce(
        (latest, skillUse) => Math.max(latest, Number(skillUse.id) || 0),
        0,
    );
}
