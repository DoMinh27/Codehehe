from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from matches.services.db import retry_transient_db_lock
from social.models import (
    DirectMatchInvitation,
    FriendRequest,
    Friendship,
    UserBlock,
    UserPresence,
)


class SocialConflict(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def retry_social_write(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return retry_transient_db_lock(lambda: function(*args, **kwargs))

    return wrapper


def canonical_user_ids(first_id, second_id):
    if first_id == second_id:
        raise SocialConflict("SELF_NOT_ALLOWED", "Bạn không thể thực hiện thao tác này với chính mình")
    return tuple(sorted((first_id, second_id)))


def friendship_query(user):
    return Friendship.objects.filter(Q(user_low=user) | Q(user_high=user))


def _pair_filter(first_id, second_id):
    low_id, high_id = canonical_user_ids(first_id, second_id)
    return {"user_low_id": low_id, "user_high_id": high_id}


def _close_expired_pair_requests(*, low_id, high_id, now):
    FriendRequest.objects.filter(
        user_low_id=low_id,
        user_high_id=high_id,
        status=FriendRequest.Status.PENDING,
        expires_at__lte=now,
    ).update(status=FriendRequest.Status.CANCELLED, responded_at=now)


def are_blocked(first_id, second_id):
    return UserBlock.objects.filter(
        Q(blocker_id=first_id, blocked_id=second_id)
        | Q(blocker_id=second_id, blocked_id=first_id)
    ).exists()


@retry_social_write
@transaction.atomic
def send_friend_request(*, requester, username, now=None):
    now = now or timezone.now()
    user_model = get_user_model()
    recipient = user_model.objects.filter(username=username, is_active=True).first()
    if recipient is None or recipient.pk == requester.pk or are_blocked(requester.pk, recipient.pk):
        raise SocialConflict("USER_UNAVAILABLE", "Không thể gửi lời mời tới tài khoản này")

    low_id, high_id = canonical_user_ids(requester.pk, recipient.pk)
    list(
        user_model.objects.select_for_update()
        .filter(pk__in=[low_id, high_id])
        .order_by("pk")
    )
    _close_expired_pair_requests(low_id=low_id, high_id=high_id, now=now)

    if Friendship.objects.filter(user_low_id=low_id, user_high_id=high_id).exists():
        raise SocialConflict("ALREADY_FRIENDS", "Hai bạn đã là bạn bè")

    pending = FriendRequest.objects.filter(
        user_low_id=low_id,
        user_high_id=high_id,
        status=FriendRequest.Status.PENDING,
        expires_at__gt=now,
    ).first()
    if pending:
        code = "INCOMING_PENDING" if pending.requester_id != requester.pk else "ALREADY_PENDING"
        raise SocialConflict(code, "Lời mời kết bạn này đang chờ phản hồi")

    cooldown_start = now - timedelta(
        seconds=settings.SOCIAL_FRIEND_DECLINE_COOLDOWN_SECONDS
    )
    if FriendRequest.objects.filter(
        requester=requester,
        user_low_id=low_id,
        user_high_id=high_id,
        status=FriendRequest.Status.DECLINED,
        responded_at__gt=cooldown_start,
    ).exists():
        raise SocialConflict("DECLINE_COOLDOWN", "Bạn cần chờ trước khi gửi lại lời mời")

    if friendship_query(requester).count() >= settings.SOCIAL_MAX_FRIENDS:
        raise SocialConflict("FRIEND_LIMIT", "Danh sách bạn bè của bạn đã đạt giới hạn")
    if FriendRequest.objects.filter(
        requester=requester,
        status=FriendRequest.Status.PENDING,
        expires_at__gt=now,
    ).count() >= settings.SOCIAL_MAX_PENDING_SENT_REQUESTS:
        raise SocialConflict("PENDING_LIMIT", "Bạn đang có quá nhiều lời mời chờ phản hồi")
    if FriendRequest.objects.filter(
        requester=requester,
        created_at__gt=now - timedelta(hours=1),
    ).count() >= settings.SOCIAL_FRIEND_REQUESTS_PER_HOUR:
        raise SocialConflict("RATE_LIMITED", "Bạn đã gửi quá nhiều lời mời, hãy thử lại sau")

    try:
        return FriendRequest.objects.create(
            user_low_id=low_id,
            user_high_id=high_id,
            requester=requester,
            expires_at=now + timedelta(seconds=settings.SOCIAL_FRIEND_REQUEST_TTL_SECONDS),
        )
    except IntegrityError as error:
        raise SocialConflict("ALREADY_PENDING", "Lời mời kết bạn này đang chờ phản hồi") from error


@retry_social_write
@transaction.atomic
def act_on_friend_request(*, actor, request_id, action, now=None):
    now = now or timezone.now()
    invitation = (
        FriendRequest.objects.select_for_update()
        .select_related("user_low", "user_high", "requester")
        .filter(pk=request_id)
        .first()
    )
    if invitation is None or actor.pk not in (invitation.user_low_id, invitation.user_high_id):
        raise SocialConflict("REQUEST_NOT_FOUND", "Lời mời không còn khả dụng")

    recipient_id = invitation.recipient_id
    allowed = (
        (action == "cancel" and actor.pk == invitation.requester_id)
        or (action in {"accept", "decline"} and actor.pk == recipient_id)
    )
    if not allowed:
        raise SocialConflict("ACTION_FORBIDDEN", "Bạn không thể xử lý lời mời này")

    terminal_by_action = {
        "accept": FriendRequest.Status.ACCEPTED,
        "decline": FriendRequest.Status.DECLINED,
        "cancel": FriendRequest.Status.CANCELLED,
    }
    requested_status = terminal_by_action[action]
    if invitation.status != FriendRequest.Status.PENDING:
        if invitation.status == requested_status:
            return invitation
        raise SocialConflict("REQUEST_PROCESSED", "Lời mời đã được xử lý")
    if invitation.expires_at <= now:
        invitation.status = FriendRequest.Status.CANCELLED
        invitation.responded_at = now
        invitation.save(update_fields=["status", "responded_at"])
        raise SocialConflict("REQUEST_EXPIRED", "Lời mời đã hết hạn")

    if action == "accept":
        user_model = get_user_model()
        list(
            user_model.objects.select_for_update()
            .filter(pk__in=[invitation.user_low_id, invitation.user_high_id])
            .order_by("pk")
        )
        if are_blocked(invitation.user_low_id, invitation.user_high_id):
            raise SocialConflict("REQUEST_UNAVAILABLE", "Lời mời không còn khả dụng")
        for user_id in (invitation.user_low_id, invitation.user_high_id):
            if friendship_query(user_model.objects.get(pk=user_id)).count() >= settings.SOCIAL_MAX_FRIENDS:
                raise SocialConflict("FRIEND_LIMIT", "Một danh sách bạn bè đã đạt giới hạn")
        Friendship.objects.get_or_create(
            user_low_id=invitation.user_low_id,
            user_high_id=invitation.user_high_id,
        )

    invitation.status = requested_status
    invitation.responded_at = now
    invitation.save(update_fields=["status", "responded_at"])
    return invitation


@retry_social_write
@transaction.atomic
def remove_friend(*, actor, other_user_id):
    pair = _pair_filter(actor.pk, other_user_id)
    deleted, _ = Friendship.objects.filter(**pair).delete()
    if not deleted:
        raise SocialConflict("FRIEND_NOT_FOUND", "Quan hệ bạn bè không còn tồn tại")
    now = timezone.now()
    DirectMatchInvitation.objects.filter(
        Q(inviter_id=actor.pk, invitee_id=other_user_id)
        | Q(inviter_id=other_user_id, invitee_id=actor.pk),
        status=DirectMatchInvitation.Status.PENDING,
    ).update(status=DirectMatchInvitation.Status.CANCELLED, responded_at=now)


@retry_social_write
@transaction.atomic
def block_user(*, actor, other_user_id, now=None):
    now = now or timezone.now()
    pair = _pair_filter(actor.pk, other_user_id)
    user_model = get_user_model()
    target = user_model.objects.filter(pk=other_user_id, is_active=True).first()
    if target is None:
        raise SocialConflict("USER_UNAVAILABLE", "Không thể thực hiện thao tác với tài khoản này")
    UserBlock.objects.get_or_create(blocker=actor, blocked=target)
    Friendship.objects.filter(**pair).delete()
    FriendRequest.objects.filter(
        **pair,
        status=FriendRequest.Status.PENDING,
    ).update(status=FriendRequest.Status.CANCELLED, responded_at=now)
    RematchRequest.objects.filter(
        Q(requester_id=actor.pk, recipient_id=other_user_id)
        | Q(requester_id=other_user_id, recipient_id=actor.pk),
        status=RematchRequest.Status.PENDING,
    ).update(status=RematchRequest.Status.CANCELLED, responded_at=now)
    DirectMatchInvitation.objects.filter(
        Q(inviter_id=actor.pk, invitee_id=other_user_id)
        | Q(inviter_id=other_user_id, invitee_id=actor.pk),
        status=DirectMatchInvitation.Status.PENDING,
    ).update(status=DirectMatchInvitation.Status.CANCELLED, responded_at=now)


def unblock_user(*, actor, other_user_id):
    UserBlock.objects.filter(blocker=actor, blocked_id=other_user_id).delete()


@dataclass(frozen=True)
class PresenceProjection:
    user: object
    status: str
    status_label: str
    match_invitation: object | None = None


PRESENCE_LABELS = {
    "READY": "Sẵn sàng",
    "WAITING": "Trong phòng",
    "PLAYING": "Đang trong trận",
    "INACTIVE": "Không hoạt động",
}
PRESENCE_ORDER = {"READY": 0, "WAITING": 1, "PLAYING": 2, "INACTIVE": 3}


def _friend_users(user):
    friendships = friendship_query(user).select_related("user_low", "user_high")
    return [friendship.other_user(user) for friendship in friendships]


def project_friend_presence(*, user, now=None):
    now = now or timezone.now()
    friends = _friend_users(user)
    friend_ids = [friend.pk for friend in friends]
    presences = {
        presence.user_id: presence
        for presence in UserPresence.objects.filter(user_id__in=friend_ids)
    }
    active_matches = {
        player.user_id: player.match.status
        for player in MatchPlayer.objects.select_related("match")
        .filter(user_id__in=friend_ids, is_active=True)
        .only("user_id", "match__status")
    }
    blocked_ids = set(
        UserBlock.objects.filter(
            Q(blocker=user, blocked_id__in=friend_ids)
            | Q(blocked=user, blocker_id__in=friend_ids)
        ).values_list("blocker_id", "blocked_id")
    )
    hidden_by_block = {
        other_id
        for pair in blocked_ids
        for other_id in pair
        if other_id != user.pk
    }
    match_invitations = {}
    pending_match_invitations = DirectMatchInvitation.objects.filter(
        Q(inviter=user, invitee_id__in=friend_ids)
        | Q(invitee=user, inviter_id__in=friend_ids),
        status=DirectMatchInvitation.Status.PENDING,
        expires_at__gt=now,
    )
    for invitation in pending_match_invitations:
        other_id = (
            invitation.invitee_id
            if invitation.inviter_id == user.pk
            else invitation.inviter_id
        )
        match_invitations[other_id] = invitation
    cutoff = now - timedelta(seconds=settings.SOCIAL_PRESENCE_TTL_SECONDS)
    rows = []
    for friend in friends:
        presence = presences.get(friend.pk)
        status = "INACTIVE"
        if (
            friend.pk not in hidden_by_block
            and presence is not None
            and presence.show_presence_to_friends
        ):
            match_status = active_matches.get(friend.pk)
            if match_status == Match.Status.WAITING:
                status = "WAITING"
            elif match_status == Match.Status.PLAYING:
                status = "PLAYING"
            elif presence.last_seen_at and presence.last_seen_at > cutoff:
                status = "READY"
        rows.append(
            PresenceProjection(
                friend,
                status,
                PRESENCE_LABELS[status],
                match_invitations.get(friend.pk),
            )
        )
    rows.sort(key=lambda row: (PRESENCE_ORDER[row.status], row.user.username, row.user.pk))
    return rows


def heartbeat_presence(*, user, now=None):
    now = now or timezone.now()
    presence, created = UserPresence.objects.get_or_create(user=user)
    throttle_before = now - timedelta(seconds=settings.SOCIAL_PRESENCE_HEARTBEAT_SECONDS)
    if created or presence.last_seen_at is None or presence.last_seen_at <= throttle_before:
        presence.last_seen_at = now
        presence.save(update_fields=["last_seen_at", "updated_at"])
    return presence


def set_presence_privacy(*, user, visible):
    presence, _ = UserPresence.objects.get_or_create(user=user)
    if presence.show_presence_to_friends != visible:
        presence.show_presence_to_friends = visible
        presence.save(update_fields=["show_presence_to_friends", "updated_at"])
    return presence
