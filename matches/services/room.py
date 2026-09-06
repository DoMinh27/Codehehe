"""Room creation, joining, active-membership, and leaving rules."""

from collections.abc import Callable
from dataclasses import dataclass
import secrets
import string

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from matches.integrity import current_integrity_policy
from matches.models import Match, MatchPlayer
from matches.rules import MatchRules, current_match_rules

from .db import retry_transient_db_lock

ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits
ROOM_CODE_LENGTH = 6


class RoomError(Exception):
    """Base class for expected room failures."""


class InvalidRoomCodeError(RoomError):
    """Raised when a room code has an invalid format."""


class RoomNotFoundError(RoomError):
    """Raised when no room has the requested code."""


class RoomNotWaitingError(RoomError):
    """Raised when a room no longer accepts players."""


class AlreadyJoinedError(RoomError):
    """Raised when a user is already a player in the room."""


class RoomFullError(RoomError):
    """Raised when a third player tries to join."""


class RoomCodeGenerationError(RoomError):
    """Raised when a unique room code cannot be generated."""


class ActiveMatchExistsError(RoomError):
    """Raised when a player already has a waiting or playing match."""

    def __init__(self, match: Match):
        self.match = match
        super().__init__("Bạn đang có một phòng hoặc trận đấu chưa kết thúc")


class RoomLeaveError(RoomError):
    """Raised when a player cannot leave the requested waiting room."""


def generate_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def normalize_room_code(room_code: str) -> str:
    if not isinstance(room_code, str):
        raise InvalidRoomCodeError("Mã phòng không hợp lệ")

    normalized = room_code.strip().upper()
    if (
        len(normalized) != ROOM_CODE_LENGTH
        or any(character not in ROOM_CODE_ALPHABET for character in normalized)
    ):
        raise InvalidRoomCodeError("Mã phòng phải gồm 6 chữ cái hoặc chữ số")
    return normalized


def get_active_match_player(*, user) -> MatchPlayer | None:
    return (
        MatchPlayer.objects.select_related("match")
        .filter(
            user=user,
            is_active=True,
            match__status__in=[Match.Status.WAITING, Match.Status.PLAYING],
        )
        .order_by("-match__started_at", "-match__created_at", "-id")
        .first()
    )


@dataclass
class CreateRoomService:
    code_generator: Callable[[], str] = generate_room_code
    rules_provider: Callable[[], MatchRules] = current_match_rules
    max_attempts: int = 10

    def create(self, *, user) -> Match:
        active_player = get_active_match_player(user=user)
        if active_player is not None:
            raise ActiveMatchExistsError(active_player.match)

        rules = self.rules_provider()
        integrity_policy = (
            current_integrity_policy() if settings.MATCH_INTEGRITY_ENABLED else None
        )
        for _ in range(self.max_attempts):
            room_code = normalize_room_code(self.code_generator())
            try:
                return retry_transient_db_lock(
                    lambda: self._create_once(
                        user=user,
                        room_code=room_code,
                        rules=rules,
                        integrity_policy=integrity_policy,
                    )
                )
            except IntegrityError:
                active_player = get_active_match_player(user=user)
                if active_player is not None:
                    raise ActiveMatchExistsError(active_player.match) from None
                if Match.objects.filter(room_code=room_code).exists():
                    continue
                raise

        raise RoomCodeGenerationError("Không thể tạo mã phòng. Vui lòng thử lại")

    @staticmethod
    def _create_once(
        *,
        user,
        room_code: str,
        rules: MatchRules,
        integrity_policy,
    ) -> Match:
        with transaction.atomic():
            match = Match.objects.create(
                room_code=room_code,
                host=user,
                status=Match.Status.WAITING,
                duration_seconds=rules.match_duration_seconds,
                ruleset_version=rules.version,
                rules_snapshot=rules.to_snapshot(),
                ai_review_enabled=settings.AI_REVIEW_ENABLED,
                integrity_monitor_enabled=integrity_policy is not None,
                integrity_policy_snapshot=(
                    integrity_policy.to_snapshot() if integrity_policy else {}
                ),
            )
            MatchPlayer.objects.create(
                match=match,
                user=user,
                is_host=True,
                slot=1,
                is_active=True,
            )
            return match


class JoinRoomService:
    def join(self, *, user, room_code: str) -> MatchPlayer:
        normalized_code = normalize_room_code(room_code)
        active_player = get_active_match_player(user=user)
        if active_player is not None:
            if active_player.match.room_code == normalized_code:
                raise AlreadyJoinedError("Bạn đã tham gia phòng này")
            raise ActiveMatchExistsError(active_player.match)

        try:
            return retry_transient_db_lock(
                lambda: self._join_once(user=user, room_code=normalized_code)
            )
        except IntegrityError:
            active_player = get_active_match_player(user=user)
            if active_player is not None:
                if active_player.match.room_code == normalized_code:
                    raise AlreadyJoinedError("Bạn đã tham gia phòng này") from None
                raise ActiveMatchExistsError(active_player.match) from None
            try:
                match = Match.objects.get(room_code=normalized_code)
            except Match.DoesNotExist as error:
                raise RoomNotFoundError("Không tìm thấy phòng") from error
            if match.players.filter(slot=2).exists():
                raise RoomFullError("Phòng đã đầy") from None
            raise

    @staticmethod
    def _join_once(*, user, room_code: str) -> MatchPlayer:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(room_code=room_code)
            except Match.DoesNotExist as error:
                raise RoomNotFoundError("Không tìm thấy phòng") from error

            if match.status != Match.Status.WAITING:
                raise RoomNotWaitingError("Phòng không còn ở trạng thái chờ")
            if MatchPlayer.objects.filter(match=match, user=user).exists():
                raise AlreadyJoinedError("Bạn đã tham gia phòng này")
            if MatchPlayer.objects.filter(match=match, slot=2).exists():
                raise RoomFullError("Phòng đã đầy")

            return MatchPlayer.objects.create(
                match=match,
                user=user,
                is_host=False,
                slot=2,
                is_active=True,
            )


class LeaveRoomService:
    """Leave a waiting room; a host leaving cancels it for everyone."""

    def leave(self, *, user, room_code: str) -> Match:
        normalized_code = normalize_room_code(room_code)
        return retry_transient_db_lock(
            lambda: self._leave_once(user=user, room_code=normalized_code)
        )

    @staticmethod
    def _leave_once(*, user, room_code: str) -> Match:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(room_code=room_code)
            except Match.DoesNotExist as error:
                raise RoomNotFoundError("Không tìm thấy phòng") from error
            try:
                player = MatchPlayer.objects.select_for_update().get(
                    match=match,
                    user=user,
                )
            except MatchPlayer.DoesNotExist as error:
                raise RoomLeaveError("Bạn không thuộc phòng này") from error
            if match.status != Match.Status.WAITING:
                raise RoomLeaveError("Chỉ có thể rời phòng trước khi trận bắt đầu")

            if player.is_host:
                match.status = Match.Status.CANCELLED
                match.ended_at = timezone.now()
                match.save(update_fields=["status", "ended_at", "updated_at"])
                MatchPlayer.objects.filter(match=match).update(is_active=False)
            else:
                player.delete()
            return match
