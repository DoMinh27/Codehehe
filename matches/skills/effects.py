from django.db.models import Q


def active_effect_condition(now):
    return Q(
        cancelled_at__isnull=True,
        consumed_at__isnull=True,
        expires_at__gt=now,
    )


def active_effects_for_player(*, player, now, lock=False):
    from matches.models import SkillEffect

    queryset = SkillEffect.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(
        active_effect_condition(now),
        skill_use__target_player=player,
    )
