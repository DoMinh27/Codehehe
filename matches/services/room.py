"""Room creation and joining rules."""

from collections.abc import Callable
from dataclasses import dataclass
import secrets
import string

from django.db import IntegrityError, transaction

from matches.models import Match, MatchPlayer

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


def generate_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def normalize_room_code(room_code: str) -> str:
    if not isinstance(room_code, str):
        raise InvalidRoomCodeError("Mã phòng không hợp lệ.")

    normalized = room_code.strip().upper()
    if (
        len(normalized) != ROOM_CODE_LENGTH
        or any(character not in ROOM_CODE_ALPHABET for character in normalized)
    ):
        raise InvalidRoomCodeError("Mã phòng phải gồm 6 chữ cái hoặc chữ số.")
    return normalized


@dataclass
class CreateRoomService:
    code_generator: Callable[[], str] = generate_room_code
    max_attempts: int = 10

    def create(self, *, user) -> Match:
        for _ in range(self.max_attempts):
            room_code = normalize_room_code(self.code_generator())
            try:
                with transaction.atomic():
                    match = Match.objects.create(
                        room_code=room_code,
                        host=user,
                        status=Match.Status.WAITING,
                    )
                    MatchPlayer.objects.create(
                        match=match,
                        user=user,
                        is_host=True,
                    )
                return match
            except IntegrityError:
                if Match.objects.filter(room_code=room_code).exists():
                    continue
                raise

        raise RoomCodeGenerationError("Không thể tạo mã phòng. Vui lòng thử lại.")


class JoinRoomService:
    def join(self, *, user, room_code: str) -> MatchPlayer:
        normalized_code = normalize_room_code(room_code)

        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(room_code=normalized_code)
            except Match.DoesNotExist as error:
                raise RoomNotFoundError("Không tìm thấy phòng.") from error

            if match.status != Match.Status.WAITING:
                raise RoomNotWaitingError("Phòng không còn ở trạng thái chờ.")
            if MatchPlayer.objects.filter(match=match, user=user).exists():
                raise AlreadyJoinedError("Bạn đã tham gia phòng này.")
            if MatchPlayer.objects.filter(match=match).count() >= 2:
                raise RoomFullError("Phòng đã đầy.")

            return MatchPlayer.objects.create(
                match=match,
                user=user,
                is_host=False,
            )
