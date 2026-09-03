"""Server-authoritative Fair Play event processing."""

from dataclasses import dataclass

from django.db import connection, transaction
from django.utils import timezone

from matches.integrity import IntegrityPolicy, IntegrityPolicyError
from matches.models import (
    Match,
    MatchIntegrityEvent,
    MatchIntegrityState,
    MatchPlayer,
)

from .db import retry_transient_db_lock


HEARTBEAT = "HEARTBEAT"
HIDDEN = "HIDDEN"
VISIBLE = "VISIBLE"
PAGE_LEAVE = "PAGE_LEAVE"
PAGE_RETURN = "PAGE_RETURN"
PASTE = "PASTE"
CLIENT_EVENT_KINDS = frozenset(
    {HEARTBEAT, HIDDEN, VISIBLE, PAGE_LEAVE, PAGE_RETURN, PASTE}
)
PROCESSED_EVENT_ID_LIMIT = 100


class IntegrityError(Exception):
    """Base class for expected Fair Play failures."""


class IntegrityNotFoundError(IntegrityError):
    pass


class IntegrityPermissionError(IntegrityError):
    pass


class IntegrityStateError(IntegrityError):
    pass


class IntegrityConfigurationError(IntegrityError):
    pass


@dataclass(frozen=True)
class IntegrityNotice:
    code: str
    message: str

    def as_dict(self):
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class IntegrityBatchResult:
    accepted_event_ids: tuple[str, ...]
    notice: IntegrityNotice | None


def _duration_ms(started_at, ended_at) -> int:
    return max(0, round((ended_at - started_at).total_seconds() * 1000))


def _save_state(state):
    state.save(
        update_fields=[
            "last_heartbeat_at",
            "active_absence_started_at",
            "active_absence_kind",
            "active_absence_id",
            "strike_count",
            "away_duration_ms",
            "paste_count",
            "paste_character_count",
            "is_flagged",
            "flagged_at",
            "flag_reason",
            "processed_event_ids",
            "updated_at",
        ]
    )


def _flag_state(*, state, match, player, reason, now):
    if state.is_flagged:
        return
    state.is_flagged = True
    state.flagged_at = now
    state.flag_reason = reason
    MatchIntegrityEvent.objects.get_or_create(
        match=match,
        player=player,
        event_key="flagged",
        defaults={
            "kind": MatchIntegrityEvent.Kind.FLAGGED,
            "severity": MatchIntegrityEvent.Severity.WARNING,
            "started_at": now,
            "recorded_at": now,
            "value": state.strike_count,
        },
    )


def _evaluate_absence_flag(*, state, match, player, policy, now):
    if state.strike_count >= policy.flag_strikes:
        _flag_state(
            state=state,
            match=match,
            player=player,
            reason=MatchIntegrityState.FlagReason.STRIKES,
            now=now,
        )
    elif state.away_duration_ms >= policy.flag_total_seconds * 1000:
        _flag_state(
            state=state,
            match=match,
            player=player,
            reason=MatchIntegrityState.FlagReason.AWAY_TIME,
            now=now,
        )


def _begin_absence(*, state, kind, event_id, now):
    if state.active_absence_started_at is None:
        state.active_absence_started_at = now
        state.active_absence_kind = kind
        state.active_absence_id = event_id
        return
    if kind == MatchIntegrityState.AbsenceKind.PAGE:
        state.active_absence_kind = kind


def _close_absence(*, state, match, player, policy, now):
    started_at = state.active_absence_started_at
    if started_at is None:
        return None
    absence_kind = state.active_absence_kind
    absence_id = state.active_absence_id
    state.active_absence_started_at = None
    state.active_absence_kind = ""
    state.active_absence_id = ""
    duration_ms = _duration_ms(started_at, now)
    if duration_ms < policy.ignore_below_seconds * 1000:
        return None

    event_kind = (
        MatchIntegrityEvent.Kind.PAGE_AWAY
        if absence_kind == MatchIntegrityState.AbsenceKind.PAGE
        else MatchIntegrityEvent.Kind.TAB_AWAY
    )
    is_strike = duration_ms >= policy.strike_seconds * 1000
    _event, created = MatchIntegrityEvent.objects.get_or_create(
        match=match,
        player=player,
        event_key=f"absence:{absence_id}",
        defaults={
            "kind": event_kind,
            "severity": (
                MatchIntegrityEvent.Severity.WARNING
                if is_strike
                else MatchIntegrityEvent.Severity.INFO
            ),
            "started_at": started_at,
            "ended_at": now,
            "duration_ms": duration_ms,
            "recorded_at": now,
        },
    )
    if not created:
        return None

    state.away_duration_ms += duration_ms
    if is_strike:
        state.strike_count += 1
    _evaluate_absence_flag(
        state=state,
        match=match,
        player=player,
        policy=policy,
        now=now,
    )
    if not is_strike:
        return None
    seconds = max(1, round(duration_ms / 1000))
    return IntegrityNotice(
        code="FOCUS_VIOLATION_RECORDED",
        message=(
            f"Hệ thống đã ghi nhận bạn rời màn hình trong {seconds} giây."
        ),
    )


def _record_connection_gap(*, state, match, player, policy, now):
    last_heartbeat_at = state.last_heartbeat_at
    if last_heartbeat_at is None or state.active_absence_started_at is not None:
        return None
    duration_ms = _duration_ms(last_heartbeat_at, now)
    if duration_ms < policy.connection_gap_seconds * 1000:
        return None
    event_key = f"gap:{last_heartbeat_at.isoformat()}"
    _event, created = MatchIntegrityEvent.objects.get_or_create(
        match=match,
        player=player,
        event_key=event_key,
        defaults={
            "kind": MatchIntegrityEvent.Kind.CONNECTION_GAP,
            "severity": MatchIntegrityEvent.Severity.WARNING,
            "started_at": last_heartbeat_at,
            "ended_at": now,
            "duration_ms": duration_ms,
            "recorded_at": now,
        },
    )
    if not created:
        return None
    _flag_state(
        state=state,
        match=match,
        player=player,
        reason=MatchIntegrityState.FlagReason.CONNECTION_GAP,
        now=now,
    )
    seconds = max(1, round(duration_ms / 1000))
    return IntegrityNotice(
        code="CONNECTION_GAP_RECORDED",
        message=f"Hệ thống đã ghi nhận kết nối bị gián đoạn trong {seconds} giây.",
    )


def _record_paste(*, state, match, player, event_id, character_count, now):
    _event, created = MatchIntegrityEvent.objects.get_or_create(
        match=match,
        player=player,
        event_key=f"paste:{event_id}",
        defaults={
            "kind": MatchIntegrityEvent.Kind.PASTE,
            "severity": MatchIntegrityEvent.Severity.INFO,
            "started_at": now,
            "recorded_at": now,
            "value": character_count,
        },
    )
    if created:
        state.paste_count += 1
        state.paste_character_count += character_count


class MatchIntegrityService:
    def record(self, *, user, match_id: int, events: list[dict], now=None):
        return retry_transient_db_lock(
            lambda: self._record_once(
                user=user,
                match_id=match_id,
                events=events,
                now=now,
            )
        )

    @staticmethod
    def _record_once(*, user, match_id: int, events: list[dict], now=None):
        recorded_at = now or timezone.now()
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise IntegrityNotFoundError("Không tìm thấy trận đấu.") from error
            try:
                player = MatchPlayer.objects.select_for_update().get(
                    match=match,
                    user=user,
                )
            except MatchPlayer.DoesNotExist as error:
                raise IntegrityPermissionError(
                    "Bạn không thuộc trận đấu này."
                ) from error
            if not match.integrity_monitor_enabled:
                raise IntegrityStateError("Fair Play Monitor không được bật.")
            if match.status != Match.Status.PLAYING:
                raise IntegrityStateError("Trận đấu không ở trạng thái đang chơi.")
            try:
                policy = IntegrityPolicy.from_snapshot(
                    match.integrity_policy_snapshot
                )
            except IntegrityPolicyError as error:
                raise IntegrityConfigurationError(
                    "Cấu hình Fair Play không hợp lệ."
                ) from error
            try:
                state = MatchIntegrityState.objects.select_for_update().get(
                    player=player
                )
            except MatchIntegrityState.DoesNotExist as error:
                raise IntegrityConfigurationError(
                    "Trạng thái Fair Play chưa được khởi tạo."
                ) from error

            processed_ids = list(state.processed_event_ids or [])
            processed_set = set(processed_ids)
            accepted_ids = []
            notice = None
            for event in events:
                event_id = event["event_id"]
                accepted_ids.append(event_id)
                if event_id in processed_set:
                    continue
                kind = event["kind"]
                event_notice = None
                if kind == PAGE_RETURN:
                    if state.active_absence_started_at is not None:
                        event_notice = _close_absence(
                            state=state,
                            match=match,
                            player=player,
                            policy=policy,
                            now=recorded_at,
                        )
                    else:
                        event_notice = _record_connection_gap(
                            state=state,
                            match=match,
                            player=player,
                            policy=policy,
                            now=recorded_at,
                        )
                elif kind == HEARTBEAT:
                    event_notice = _record_connection_gap(
                        state=state,
                        match=match,
                        player=player,
                        policy=policy,
                        now=recorded_at,
                    )
                elif kind == VISIBLE:
                    event_notice = _close_absence(
                        state=state,
                        match=match,
                        player=player,
                        policy=policy,
                        now=recorded_at,
                    )
                elif kind == HIDDEN:
                    _begin_absence(
                        state=state,
                        kind=MatchIntegrityState.AbsenceKind.TAB,
                        event_id=event_id,
                        now=recorded_at,
                    )
                elif kind == PAGE_LEAVE:
                    _begin_absence(
                        state=state,
                        kind=MatchIntegrityState.AbsenceKind.PAGE,
                        event_id=event_id,
                        now=recorded_at,
                    )
                elif kind == PASTE:
                    _record_paste(
                        state=state,
                        match=match,
                        player=player,
                        event_id=event_id,
                        character_count=event["character_count"],
                        now=recorded_at,
                    )
                processed_ids.append(event_id)
                processed_set.add(event_id)
                if event_notice is not None:
                    notice = event_notice

            state.last_heartbeat_at = recorded_at
            state.processed_event_ids = processed_ids[-PROCESSED_EVENT_ID_LIMIT:]
            _save_state(state)
            return IntegrityBatchResult(
                accepted_event_ids=tuple(accepted_ids),
                notice=notice,
            )


def finalize_match_integrity(*, match, players, now):
    """Close open Fair Play intervals in the match lifecycle transaction."""
    if not match.integrity_monitor_enabled:
        return
    if not connection.in_atomic_block:
        raise RuntimeError("Fair Play finalization must share the match transaction.")
    try:
        policy = IntegrityPolicy.from_snapshot(match.integrity_policy_snapshot)
    except IntegrityPolicyError:
        return
    states = {
        state.player_id: state
        for state in MatchIntegrityState.objects.select_for_update().filter(
            player__in=players
        )
    }
    for player in players:
        state = states.get(player.pk)
        if state is None:
            continue
        if state.active_absence_started_at is not None:
            _close_absence(
                state=state,
                match=match,
                player=player,
                policy=policy,
                now=now,
            )
        else:
            _record_connection_gap(
                state=state,
                match=match,
                player=player,
                policy=policy,
                now=now,
            )
        _save_state(state)
