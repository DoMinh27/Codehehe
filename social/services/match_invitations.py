"""Direct friend challenges and atomic two-player room creation."""

from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from matches.models import MatchPlayer, RematchRequest
from matches.services.db import retry_transient_db_lock
from matches.services.room import CreatePairRoomService, CreateRoomService
from social.models import DirectMatchInvitation, Friendship, UserBlock, UserPresence
from social.services.friends import canonical_user_ids


class MatchInvitationError(Exception):
    def __init__(self, code, message, status=409):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _pair_key(first_id, second_id):
    return DirectMatchInvitation.make_pair_key(first_id, second_id)


def _friendship_exists(first_id, second_id):
    low_id, high_id = canonical_user_ids(first_id, second_id)
    return Friendship.objects.filter(
        user_low_id=low_id,
        user_high_id=high_id,
    ).exists()


def _blocked(first_id, second_id):
    return UserBlock.objects.filter(
        Q(blocker_id=first_id, blocked_id=second_id)
        | Q(blocker_id=second_id, blocked_id=first_id)
    ).exists()


def ready_user_ids(user_ids, *, now=None):
    """Return users whose public presence currently qualifies as ready."""
    now = now or timezone.now()
    user_ids = set(user_ids)
    cutoff = now - timedelta(seconds=settings.SOCIAL_PRESENCE_TTL_SECONDS)
    ready = set(
        UserPresence.objects.filter(
            user_id__in=user_ids,
            show_presence_to_friends=True,
            last_seen_at__gt=cutoff,
        ).values_list("user_id", flat=True)
    )
    busy = set(
        MatchPlayer.objects.filter(user_id__in=user_ids, is_active=True).values_list(
            "user_id", flat=True
        )
    )
    return ready - busy


def _require_ready(first_id, second_id, *, now):
    if ready_user_ids((first_id, second_id), now=now) != {first_id, second_id}:
        raise MatchInvitationError(
            "PLAYERS_UNAVAILABLE",
            "Cả hai người chơi phải ở trạng thái Sẵn sàng",
        )


def _room_url(invitation):
    if invitation.new_match_id is None:
        return None
    return reverse(
        "waiting-room",
        kwargs={"room_code": invitation.new_match.room_code},
    )


def invitation_result(invitation):
    return {
        "ok": True,
        "status": invitation.status,
        "room_url": _room_url(invitation),
    }


@transaction.atomic
def _send_once(*, inviter, invitee_id, now):
    user_model = get_user_model()
    invitee = user_model.objects.filter(pk=invitee_id, is_active=True).first()
    if invitee is None or invitee.pk == inviter.pk:
        raise MatchInvitationError(
            "RECIPIENT_UNAVAILABLE",
            "Không thể gửi lời mời đấu tới tài khoản này",
            404,
        )

    user_ids = sorted((inviter.pk, invitee.pk))
    users = list(
        user_model.objects.select_for_update()
        .filter(pk__in=user_ids, is_active=True)
        .order_by("pk")
    )
    if len(users) != 2 or not _friendship_exists(inviter.pk, invitee.pk) or _blocked(
        inviter.pk, invitee.pk
    ):
        raise MatchInvitationError(
            "RECIPIENT_UNAVAILABLE",
            "Không thể gửi lời mời đấu tới tài khoản này",
            404,
        )

    pair_key = _pair_key(inviter.pk, invitee.pk)
    DirectMatchInvitation.objects.filter(
        pair_key=pair_key,
        status=DirectMatchInvitation.Status.PENDING,
        expires_at__lte=now,
    ).update(status=DirectMatchInvitation.Status.CANCELLED, responded_at=now)
    if DirectMatchInvitation.objects.filter(
        pair_key=pair_key,
        status=DirectMatchInvitation.Status.PENDING,
        expires_at__gt=now,
    ).exists():
        raise MatchInvitationError(
            "INVITATION_PENDING",
            "Lời mời đấu giữa hai bạn đang chờ phản hồi",
        )

    _require_ready(inviter.pk, invitee.pk, now=now)
    pending = DirectMatchInvitation.objects.filter(
        status=DirectMatchInvitation.Status.PENDING,
        expires_at__gt=now,
    )
    limit = settings.SOCIAL_MAX_PENDING_MATCH_INVITES
    if pending.filter(inviter=inviter).count() >= limit:
        raise MatchInvitationError(
            "OUTGOING_LIMIT",
            "Bạn đang có quá nhiều lời mời đấu chờ phản hồi",
        )
    if pending.filter(invitee=invitee).count() >= limit:
        raise MatchInvitationError(
            "INCOMING_LIMIT",
            "Người chơi này đang có quá nhiều lời mời đấu",
        )
    window_start = now - timedelta(minutes=10)
    if DirectMatchInvitation.objects.filter(
        inviter=inviter,
        created_at__gt=window_start,
    ).count() >= settings.SOCIAL_MATCH_INVITES_PER_10_MINUTES:
        raise MatchInvitationError(
            "RATE_LIMITED",
            "Bạn đã gửi quá nhiều lời mời đấu, hãy thử lại sau",
        )

    return DirectMatchInvitation.objects.create(
        inviter=inviter,
        invitee=invitee,
        pair_key=pair_key,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.SOCIAL_MATCH_INVITE_TTL_SECONDS),
    )


def send_match_invitation(*, inviter, invitee_id, now=None):
    now = now or timezone.now()
    try:
        return retry_transient_db_lock(
            lambda: _send_once(inviter=inviter, invitee_id=invitee_id, now=now)
        )
    except IntegrityError as error:
        if DirectMatchInvitation.objects.filter(
            pair_key=_pair_key(inviter.pk, invitee_id),
            status=DirectMatchInvitation.Status.PENDING,
            expires_at__gt=now,
        ).exists():
            raise MatchInvitationError(
                "INVITATION_PENDING",
                "Lời mời đấu giữa hai bạn đang chờ phản hồi",
            ) from error
        raise


@dataclass
class MatchInvitationService:
    room_service: CreateRoomService = field(default_factory=CreateRoomService)

    def act(self, *, actor, invitation_id, action, now=None):
        if action not in {"accept", "decline", "cancel"}:
            raise MatchInvitationError(
                "INVALID_ACTION",
                "Hành động không hợp lệ",
                400,
            )
        now = now or timezone.now()
        try:
            return retry_transient_db_lock(
                lambda: self._act_once(
                    actor=actor,
                    invitation_id=invitation_id,
                    action=action,
                    now=now,
                )
            )
        except IntegrityError:
            invitation = DirectMatchInvitation.objects.select_related("new_match").filter(
                pk=invitation_id
            ).first()
            if (
                action == "accept"
                and invitation is not None
                and actor.pk == invitation.invitee_id
                and invitation.status == DirectMatchInvitation.Status.ACCEPTED
            ):
                return invitation
            raise MatchInvitationError(
                "INVITATION_CONFLICT",
                "Trạng thái người chơi vừa thay đổi, hãy thử lại",
            ) from None

    @transaction.atomic
    def _act_once(self, *, actor, invitation_id, action, now):
        if connection.vendor == "sqlite":
            DirectMatchInvitation.objects.filter(pk=invitation_id).update(
                status=F("status")
            )
        invitation = (
            DirectMatchInvitation.objects.select_for_update()
            .select_related("inviter", "invitee", "new_match")
            .filter(pk=invitation_id)
            .first()
        )
        if invitation is None or actor.pk not in (
            invitation.inviter_id,
            invitation.invitee_id,
        ):
            raise MatchInvitationError(
                "INVITATION_NOT_FOUND",
                "Lời mời đấu không còn khả dụng",
                404,
            )
        allowed = (
            action == "cancel" and actor.pk == invitation.inviter_id
        ) or (
            action in {"accept", "decline"} and actor.pk == invitation.invitee_id
        )
        if not allowed:
            raise MatchInvitationError(
                "ACTION_FORBIDDEN",
                "Bạn không thể xử lý lời mời đấu này",
                403,
            )

        desired = {
            "accept": DirectMatchInvitation.Status.ACCEPTED,
            "decline": DirectMatchInvitation.Status.DECLINED,
            "cancel": DirectMatchInvitation.Status.CANCELLED,
        }[action]
        if invitation.status != DirectMatchInvitation.Status.PENDING:
            if invitation.status == desired:
                return invitation
            raise MatchInvitationError(
                "INVITATION_PROCESSED",
                "Lời mời đấu đã được xử lý",
            )
        if invitation.expires_at <= now:
            invitation.status = DirectMatchInvitation.Status.CANCELLED
            invitation.responded_at = now
            invitation.save(update_fields=["status", "responded_at"])
            raise MatchInvitationError(
                "INVITATION_EXPIRED",
                "Lời mời đấu đã hết hạn",
            )

        if action == "accept":
            user_model = get_user_model()
            locked_users = list(
                user_model.objects.select_for_update()
                .filter(pk__in=[invitation.inviter_id, invitation.invitee_id], is_active=True)
                .order_by("pk")
            )
            if (
                len(locked_users) != 2
                or not _friendship_exists(invitation.inviter_id, invitation.invitee_id)
                or _blocked(invitation.inviter_id, invitation.invitee_id)
            ):
                raise MatchInvitationError(
                    "INVITATION_UNAVAILABLE",
                    "Lời mời đấu không còn khả dụng",
                )
            _require_ready(invitation.inviter_id, invitation.invitee_id, now=now)
            invitation.new_match = CreatePairRoomService(self.room_service).create(
                host=invitation.inviter,
                guest=invitation.invitee,
            )

        invitation.status = desired
        invitation.responded_at = now
        invitation.save(update_fields=["status", "responded_at", "new_match"])
        if action == "accept":
            participant_filter = Q(
                inviter_id__in=[invitation.inviter_id, invitation.invitee_id]
            ) | Q(invitee_id__in=[invitation.inviter_id, invitation.invitee_id])
            DirectMatchInvitation.objects.filter(
                participant_filter,
                status=DirectMatchInvitation.Status.PENDING,
            ).exclude(pk=invitation.pk).update(
                status=DirectMatchInvitation.Status.CANCELLED,
                responded_at=now,
            )
            RematchRequest.objects.filter(
                Q(requester_id__in=[invitation.inviter_id, invitation.invitee_id])
                | Q(recipient_id__in=[invitation.inviter_id, invitation.invitee_id]),
                status=RematchRequest.Status.PENDING,
            ).update(status=RematchRequest.Status.CANCELLED, responded_at=now)
        return invitation
