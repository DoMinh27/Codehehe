"""Small transactional, allowlisted match log and post-match presentation."""

from django.core.paginator import Paginator
from django.db import connection
from django.utils import timezone

from matches.models import Match, MatchEvent


PAYLOAD_FIELDS = {
    MatchEvent.Kind.MATCH_STARTED: {"duration_seconds": int},
    MatchEvent.Kind.PROBLEM_SOLVED: {
        "problem_id": int,
        "problem_title": str,
        "points": int,
        "score_after": int,
        "submission_id": int,
        "submitted_at": str,
    },
    MatchEvent.Kind.FIRST_SOLVE_CONFIRMED: {
        "problem_id": int,
        "problem_title": str,
        "points": int,
        "score_after": int,
        "submission_id": int,
        "submitted_at": str,
    },
    MatchEvent.Kind.REWARD_GRANTED: {
        "problem_id": int,
        "problem_title": str,
        "energy": int,
        "skill_code": str,
        "skill_name": str,
    },
    MatchEvent.Kind.SKILL_USED: {
        "skill_use_id": int,
        "skill_code": str,
        "skill_name": str,
        "energy_spent": int,
        "duration_seconds": int,
        "time_penalty_seconds": int,
        "outcome_kind": str,
        "affected_skill_code": str,
        "affected_skill_name": str,
        "effect_id": int,
        "stolen_match_skill_id": int,
    },
    MatchEvent.Kind.TYPING_COMPLETED: {"challenge_id": int, "skill_use_id": int},
    MatchEvent.Kind.PLAYER_SURRENDERED: {},
    MatchEvent.Kind.MATCH_FINISHED: {
        "reason": str,
        "is_draw": bool,
        "winner_user_id": int,
        "ended_at": str,
        "scores": list,
    },
}
SCORE_FIELDS = {"player_id": int, "user_id": int, "username": str, "score": int}


def safe_payload(kind, payload):
    """Reject accidental addition of sensitive fields, including nested data."""
    fields = PAYLOAD_FIELDS[kind]
    if not isinstance(payload, dict) or set(payload) - fields.keys():
        raise ValueError("Unsupported match event payload fields.")
    for name, value in payload.items():
        if type(value) is not fields[name]:
            raise ValueError("Invalid match event payload type.")
    if "scores" in payload:
        for row in payload["scores"]:
            if (
                not isinstance(row, dict)
                or set(row) != SCORE_FIELDS.keys()
                or any(
                    type(row[key]) is not value_type
                    for key, value_type in SCORE_FIELDS.items()
                )
            ):
                raise ValueError("Invalid match event score snapshot.")
    return payload


def record_event(
    *, match, kind, event_key, payload=None, actor=None, target=None, now=None
):
    if not match.timeline_version:
        return None
    if not connection.in_atomic_block:
        raise RuntimeError("Match events must share the business transaction.")
    for player in (actor, target):
        if player is not None and player.match_id != match.pk:
            raise ValueError("Event participants must belong to the match.")
    event, _ = MatchEvent.objects.get_or_create(
        match=match,
        event_key=event_key,
        defaults={
            "kind": kind,
            "actor": actor,
            "target": target,
            "actor_name_snapshot": actor.user.username if actor else "",
            "target_name_snapshot": target.user.username if target else "",
            "recorded_at": now or timezone.now(),
            "payload": safe_payload(kind, payload or {}),
        },
    )
    return event


def record_match_finished(*, match, players, now=None):
    if not match.timeline_version:
        return
    payload = {
        "reason": str(match.finish_reason or ""),
        "is_draw": match.is_draw,
        "ended_at": match.ended_at.isoformat(),
        "scores": [
            {
                "player_id": p.pk,
                "user_id": p.user_id,
                "username": p.user.username,
                "score": p.score,
            }
            for p in players
        ],
    }
    if match.winner_id is not None:
        payload["winner_user_id"] = match.winner_id
    record_event(
        match=match,
        kind=MatchEvent.Kind.MATCH_FINISHED,
        event_key="finished",
        payload=payload,
        now=now,
    )


def record_skill_used(*, match, skill_use, source, target, rules, now):
    if not match.timeline_version:
        return
    skill = skill_use.match_skill
    outcome = skill_use.outcome_snapshot
    payload = {
        "skill_use_id": skill_use.pk,
        "skill_code": skill.code_snapshot,
        "skill_name": skill.name_snapshot,
        "energy_spent": skill_use.energy_spent,
    }
    if skill.duration_seconds_snapshot is not None:
        payload["duration_seconds"] = skill.duration_seconds_snapshot
    if skill.code_snapshot == "TIME_DRAIN_60":
        payload["time_penalty_seconds"] = rules.time_drain_seconds
    for source_key, dest_key in (
        ("kind", "outcome_kind"),
        ("skill_code", "affected_skill_code"),
        ("skill_name", "affected_skill_name"),
        ("effect_id", "effect_id"),
        ("match_skill_id", "stolen_match_skill_id"),
    ):
        if source_key in outcome:
            payload[dest_key] = outcome[source_key]
    record_event(
        match=match,
        kind=MatchEvent.Kind.SKILL_USED,
        event_key=f"skill:{skill_use.pk}",
        actor=source,
        target=target,
        payload=payload,
        now=now,
    )


def present_event(event, started_at):
    """Explicit projection, never serialize raw payload or related models."""
    data = event.payload
    actor = event.actor_name_snapshot or "Người chơi"
    target = event.target_name_snapshot or "Người chơi"
    kind = event.kind
    if kind == MatchEvent.Kind.MATCH_STARTED:
        text = "Trận đấu bắt đầu."
    elif kind == MatchEvent.Kind.PROBLEM_SOLVED:
        text = f"{actor} giải được {data['problem_title']}: +{data['points']} điểm (tổng {data['score_after']})."
    elif kind == MatchEvent.Kind.FIRST_SOLVE_CONFIRMED:
        text = f"{actor} được xác nhận giải đầu tiên bài {data['problem_title']}: +{data['points']} điểm thưởng (tổng {data['score_after']})."
    elif kind == MatchEvent.Kind.REWARD_GRANTED:
        text = f"{actor} nhận {data['energy']} Energy và 1 lượt {data['skill_name']}."
    elif kind == MatchEvent.Kind.SKILL_USED:
        destination = "chính mình" if event.actor_id == event.target_id else target
        text = f"{actor} dùng {data['skill_name']} lên {destination}, tốn {data['energy_spent']} Energy."
        if data.get("outcome_kind") == "PURIFIED_EFFECT":
            text += f" Đã gỡ {data['affected_skill_name']}."
        elif data.get("outcome_kind") == "STOLEN_SKILL":
            text += f" Đã đánh cắp 1 lượt {data['affected_skill_name']}."
        elif "time_penalty_seconds" in data:
            text += f" Cộng {data['time_penalty_seconds']} giây phạt thời gian."
        elif "duration_seconds" in data:
            text += f" Hiệu ứng tối đa {data['duration_seconds']} giây."
    elif kind == MatchEvent.Kind.TYPING_COMPLETED:
        text = f"{actor} hoàn thành thử thách gõ chữ và được mở khóa."
    elif kind == MatchEvent.Kind.PLAYER_SURRENDERED:
        text = f"{actor} đầu hàng."
    elif kind == MatchEvent.Kind.MATCH_FINISHED:
        scoreline = " — ".join(f"{p['username']} {p['score']}" for p in data["scores"])
        reason = dict(Match.FinishReason.choices).get(data["reason"], "Kết thúc")
        winner = next(
            (
                p["username"]
                for p in data["scores"]
                if p["user_id"] == data.get("winner_user_id")
            ),
            None,
        )
        result = "Hòa" if data["is_draw"] else f"{winner} thắng"
        text = f"{result}. {scoreline}. Lý do: {reason}."
    else:
        text = "Sự kiện trận đấu."
    elapsed = (
        max(0, int((event.recorded_at - started_at).total_seconds()))
        if started_at
        else 0
    )
    return {
        "id": event.pk,
        "kind": kind,
        "label": event.get_kind_display(),
        "elapsed": f"{elapsed // 60:02d}:{elapsed % 60:02d}",
        "recorded_at": event.recorded_at,
        "text": text,
    }


def get_timeline_page(*, match, page=1):
    if match.status != Match.Status.FINISHED or not match.timeline_version:
        return None
    result = Paginator(match.events.order_by("id"), 50).get_page(page)
    result.object_list = [
        present_event(event, match.started_at) for event in result.object_list
    ]
    return result
