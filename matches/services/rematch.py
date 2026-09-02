"""One invitation per finished match; accepting creates a new room atomically."""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from matches.services.db import retry_transient_db_lock
from matches.services.room import (
    CreateRoomService,
    RoomCodeGenerationError,
    normalize_room_code,
)


INVITATION_SECONDS = 120


class RematchError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def _get_match_and_players(*, user, match_id, lock=False):
    queryset = Match.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        match = queryset.get(pk=match_id)
    except Match.DoesNotExist:
        raise RematchError("MATCH_NOT_FOUND", "Không tìm thấy trận đấu.", 404) from None
    players = list(
        MatchPlayer.objects.filter(match=match).select_related("user").order_by("id")
    )
    if not any(player.user_id == user.pk for player in players):
        raise RematchError(
            "REMATCH_FORBIDDEN", "Chỉ người tham gia trận được tái đấu.", 403
        )
    if match.status != Match.Status.FINISHED or len(players) != 2:
        raise RematchError(
            "REMATCH_NOT_AVAILABLE",
            "Chỉ có thể tái đấu sau khi trận hai người kết thúc.",
        )
    return match, players


def _available(players):
    return (
        all(p.user.is_active for p in players)
        and not MatchPlayer.objects.filter(
            user_id__in=[p.user_id for p in players],
            is_active=True,
        ).exists()
    )


def _require_available(players):
    if not _available(players):
        raise RematchError(
            "REMATCH_PLAYER_UNAVAILABLE",
            "Một người chơi không khả dụng hoặc đã vào phòng/trận khác.",
        )


def _project(*, match, players, invitation, user, now):
    status = invitation.effective_status(now) if invitation else "NONE"
    outgoing = bool(invitation and invitation.requester_id == user.pk)
    state = {
        "status": status,
        "server_time": now.isoformat(),
        "expires_at": invitation.expires_at.isoformat() if invitation else None,
        "is_requester": outgoing,
        "requester_name": None,
        "actions": [],
        "room_url": None,
        "new_match_status": None,
        "terminal": status not in {"NONE", "PENDING"},
        "unavailable_reason": "",
    }
    if invitation:
        state["requester_name"] = next(
            (p.user.username for p in players if p.user_id == invitation.requester_id),
            "Người chơi",
        )
    if status in {"NONE", "PENDING"}:
        available = _available(players)
        if not available:
            state["unavailable_reason"] = (
                "Một người chơi không khả dụng hoặc đã vào phòng/trận khác."
            )
        if status == "NONE" and available:
            state["actions"] = ["request"]
        elif status == "PENDING":
            state["actions"] = (
                ["cancel"]
                if outgoing
                else (["accept", "decline"] if available else ["decline"])
            )
    elif status == "ACCEPTED":
        new_match = invitation.new_match
        state["new_match_status"] = new_match.status
        if (
            new_match.status != Match.Status.CANCELLED
            and new_match.players.filter(user=user).exists()
        ):
            if new_match.status == Match.Status.WAITING:
                state["room_url"] = reverse(
                    "waiting-room", kwargs={"room_code": new_match.room_code}
                )
            elif new_match.status == Match.Status.PLAYING:
                state["room_url"] = reverse("battle", kwargs={"match_id": new_match.pk})
            elif new_match.status == Match.Status.FINISHED:
                state["room_url"] = reverse(
                    "match-result", kwargs={"match_id": new_match.pk}
                )
    return state


def get_rematch_state(*, user, match_id):
    match, players = _get_match_and_players(user=user, match_id=match_id)
    invitation = (
        RematchRequest.objects.select_related("new_match").filter(match=match).first()
    )
    return _project(
        match=match,
        players=players,
        invitation=invitation,
        user=user,
        now=timezone.now(),
    )


@dataclass
class RematchService:
    room_service: CreateRoomService = field(default_factory=CreateRoomService)

    def act(self, *, user, match_id, action):
        if not isinstance(action, str) or action not in {
            "request",
            "accept",
            "decline",
            "cancel",
        }:
            raise RematchError(
                "INVALID_REMATCH_ACTION", "Hành động tái đấu không hợp lệ.", 400
            )
        try:
            return retry_transient_db_lock(
                lambda: self._act_once(user=user, match_id=match_id, action=action)
            )
        except IntegrityError:
            # Unique membership/invitation constraints are the final arbiter,
            # including SQLite where SELECT FOR UPDATE does not lock rows.
            state = get_rematch_state(user=user, match_id=match_id)
            if action == "request" and state["status"] != "NONE":
                return state
            if (
                action == "accept"
                and state["status"] == "ACCEPTED"
                and not state["is_requester"]
            ):
                return state
            raise RematchError(
                "REMATCH_CONFLICT",
                "Trạng thái phòng vừa thay đổi. Vui lòng cập nhật rồi thử lại.",
            ) from None

    def _act_once(self, *, user, match_id, action):
        with transaction.atomic():
            if connection.vendor == "sqlite":
                # SQLite ignores SELECT FOR UPDATE. Acquire its writer lock
                # before reading to avoid two deferred transactions upgrading
                # their read locks at the same time. No business data changes.
                Match.objects.filter(pk=match_id).update(status=F("status"))
            match, players = _get_match_and_players(
                user=user, match_id=match_id, lock=True
            )
            invitation = (
                RematchRequest.objects.select_for_update().filter(match=match).first()
            )
            now = timezone.now()
            if action == "request":
                if invitation is None:
                    _require_available(players)
                    recipient = next(p for p in players if p.user_id != user.pk)
                    invitation = RematchRequest.objects.create(
                        match=match,
                        requester=user,
                        recipient=recipient.user,
                        created_at=now,
                        expires_at=now + timedelta(seconds=INVITATION_SECONDS),
                    )
                # Opposing simultaneous requests expose the existing invitation;
                # they do not implicitly accept it.
            else:
                if invitation is None:
                    raise RematchError(
                        "REMATCH_NOT_FOUND", "Trận này chưa có lời mời tái đấu.", 404
                    )
                allowed_user = (
                    invitation.requester_id
                    if action == "cancel"
                    else invitation.recipient_id
                )
                if user.pk != allowed_user:
                    raise RematchError(
                        "REMATCH_FORBIDDEN",
                        "Bạn không được thực hiện hành động này.",
                        403,
                    )
                desired = {
                    "accept": "ACCEPTED",
                    "decline": "DECLINED",
                    "cancel": "CANCELLED",
                }[action]
                if invitation.status != desired:
                    if invitation.effective_status(now) != "PENDING":
                        raise RematchError(
                            "REMATCH_CLOSED", "Lời mời đã được xử lý hoặc đã hết hạn."
                        )
                    if action == "accept":
                        _require_available(players)
                        invitation.new_match = self._create_pair(invitation)
                    invitation.status = desired
                    invitation.responded_at = now
                    invitation.save(
                        update_fields=["status", "responded_at", "new_match"]
                    )
            return _project(
                match=match, players=players, invitation=invitation, user=user, now=now
            )

    def _create_pair(self, invitation):
        rules = self.room_service.rules_provider()
        for _ in range(self.room_service.max_attempts):
            code = normalize_room_code(self.room_service.code_generator())
            try:
                # Savepoint allows a code collision to retry without committing
                # a room or breaking the outer acceptance transaction.
                with transaction.atomic():
                    match = self.room_service._create_once(
                        user=invitation.requester,
                        room_code=code,
                        rules=rules,
                    )
                    MatchPlayer.objects.create(
                        match=match,
                        user=invitation.recipient,
                        is_host=False,
                        slot=2,
                        is_active=True,
                    )
                    return match
            except IntegrityError:
                if Match.objects.filter(room_code=code).exists():
                    continue
                raise
        raise RoomCodeGenerationError("Không thể tạo mã phòng. Vui lòng thử lại.")
