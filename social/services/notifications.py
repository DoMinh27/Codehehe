"""Safe notification projections assembled from domain-owned records."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from social.models import FriendRequest


NOTIFICATION_VERSION = 1
NOTIFICATION_ITEM_LIMIT = 20
INCOMING_TIME_BOUND_PRIORITY = 0
INCOMING_RELATIONSHIP_PRIORITY = 1
OUTGOING_PRIORITY = 2


@dataclass(frozen=True)
class NotificationProjection:
    priority: int
    sort_at: datetime
    payload: dict


@dataclass(frozen=True)
class NotificationBatch:
    incoming_count: int
    projections: tuple[NotificationProjection, ...]
    more_url: str | None = None


class NotificationProvider(Protocol):
    def collect(self, *, user, now, limit) -> NotificationBatch: ...


def _score_by_match(match_ids):
    scores = {}
    rows = (
        MatchPlayer.objects.filter(match_id__in=match_ids)
        .only("match_id", "score", "slot", "id")
        .order_by("match_id", "slot", "id")
    )
    for player in rows:
        scores.setdefault(player.match_id, []).append(player.score)
    return scores


def _rematch_item(*, invitation, user_id, active_user_ids, scores):
    incoming = invitation.recipient_id == user_id
    actor = invitation.requester if incoming else invitation.recipient
    participants_available = (
        invitation.requester.is_active
        and invitation.recipient.is_active
        and invitation.requester_id not in active_user_ids
        and invitation.recipient_id not in active_user_ids
    )
    action_url = reverse("rematch-action", kwargs={"match_id": invitation.match_id})
    if incoming:
        actions = [
            {"code": "ACCEPT", "url": action_url},
            {"code": "DECLINE", "url": action_url},
        ]
        if not participants_available:
            actions.pop(0)
    else:
        actions = [{"code": "CANCEL", "url": action_url}]

    match_scores = scores.get(invitation.match_id, [])
    score = " — ".join(str(value) for value in match_scores[:2])
    return {
        "key": f"REMATCH:{invitation.pk}",
        "kind": "REMATCH",
        "direction": "INCOMING" if incoming else "OUTGOING",
        "actor": {
            "username": actor.username,
            "initial": (actor.username[:1] or "?").upper(),
        },
        "created_at": invitation.created_at.isoformat(),
        "expires_at": invitation.expires_at.isoformat(),
        "context": {
            "match_code": invitation.match.room_code,
            "score": score,
        },
        "context_url": reverse(
            "match-result", kwargs={"match_id": invitation.match_id}
        ),
        "actions": actions,
        "unavailable_reason": (
            "Một người chơi đã vào phòng hoặc trận khác"
            if not participants_available
            else ""
        ),
    }


class RematchNotificationProvider:
    """Project pending rematches without owning their lifecycle or actions."""

    def collect(self, *, user, now, limit):
        base = RematchRequest.objects.filter(
            Q(requester=user) | Q(recipient=user),
            status=RematchRequest.Status.PENDING,
            expires_at__gt=now,
            match__status=Match.Status.FINISHED,
        )
        incoming_count = base.filter(recipient=user).count()
        projected = (
            base.select_related("match", "requester", "recipient")
            .only(
                "id",
                "match_id",
                "match__room_code",
                "requester_id",
                "requester__username",
                "requester__is_active",
                "recipient_id",
                "recipient__username",
                "recipient__is_active",
                "created_at",
                "expires_at",
            )
        )
        invitations = list(
            projected.filter(recipient=user).order_by(
                "expires_at", "created_at", "id"
            )[:limit]
        )
        remaining = limit - len(invitations)
        if remaining:
            invitations.extend(
                projected.filter(requester=user).order_by(
                    "expires_at", "created_at", "id"
                )[:remaining]
            )

        match_ids = [invitation.match_id for invitation in invitations]
        participant_ids = {
            participant_id
            for invitation in invitations
            for participant_id in (
                invitation.requester_id,
                invitation.recipient_id,
            )
        }
        active_user_ids = set(
            MatchPlayer.objects.filter(user_id__in=participant_ids, is_active=True)
            .values_list("user_id", flat=True)
            .distinct()
        )
        scores = _score_by_match(match_ids)
        projections = tuple(
            NotificationProjection(
                priority=(
                    INCOMING_TIME_BOUND_PRIORITY
                    if invitation.recipient_id == user.pk
                    else OUTGOING_PRIORITY
                ),
                sort_at=invitation.expires_at,
                payload=_rematch_item(
                    invitation=invitation,
                    user_id=user.pk,
                    active_user_ids=active_user_ids,
                    scores=scores,
                ),
            )
            for invitation in invitations
        )
        return NotificationBatch(
            incoming_count=incoming_count,
            projections=projections,
        )


class FriendRequestNotificationProvider:
    """Project pending friend requests while the social domain owns actions."""

    def collect(self, *, user, now, limit):
        base = (
            FriendRequest.objects.filter(
                Q(user_low=user) | Q(user_high=user),
                status=FriendRequest.Status.PENDING,
                expires_at__gt=now,
            )
            .select_related("user_low", "user_high", "requester")
            .only(
                "id",
                "user_low_id",
                "user_low__username",
                "user_high_id",
                "user_high__username",
                "requester_id",
                "requester__username",
                "created_at",
                "expires_at",
            )
        )
        incoming_count = base.exclude(requester=user).count()
        total_count = base.count()
        invitations = list(
            base.exclude(requester=user).order_by("created_at", "id")[:limit]
        )
        remaining = limit - len(invitations)
        if remaining:
            invitations.extend(
                base.filter(requester=user).order_by("created_at", "id")[:remaining]
            )

        projections = []
        for invitation in invitations:
            incoming = invitation.requester_id != user.pk
            actor = invitation.requester if incoming else invitation.recipient
            action_url = reverse(
                "social:friend-request-action",
                kwargs={"request_id": invitation.pk},
            )
            actions = (
                [
                    {"code": "ACCEPT", "url": action_url},
                    {"code": "DECLINE", "url": action_url},
                ]
                if incoming
                else [{"code": "CANCEL", "url": action_url}]
            )
            payload = {
                "key": f"FRIEND_REQUEST:{invitation.pk}",
                "kind": "FRIEND_REQUEST",
                "direction": "INCOMING" if incoming else "OUTGOING",
                "actor": {
                    "username": actor.username,
                    "initial": (actor.username[:1] or "?").upper(),
                },
                "created_at": invitation.created_at.isoformat(),
                "expires_at": invitation.expires_at.isoformat(),
                "context": {},
                "context_url": f"{reverse('social:friends')}?tab=requests",
                "actions": actions,
                "unavailable_reason": "",
            }
            projections.append(
                NotificationProjection(
                    priority=(
                        INCOMING_RELATIONSHIP_PRIORITY if incoming else OUTGOING_PRIORITY
                    ),
                    sort_at=invitation.created_at,
                    payload=payload,
                )
            )
        return NotificationBatch(
            incoming_count=incoming_count,
            projections=tuple(projections),
            more_url=(
                f"{reverse('social:friends')}?tab=requests"
                if total_count > len(invitations)
                else None
            ),
        )


NOTIFICATION_PROVIDERS: tuple[NotificationProvider, ...] = (
    RematchNotificationProvider(),
    FriendRequestNotificationProvider(),
)


def get_notification_state(*, user, now=None):
    """Return pending notification items visible to one authenticated user."""
    now = now or timezone.now()
    batches = [
        provider.collect(user=user, now=now, limit=NOTIFICATION_ITEM_LIMIT)
        for provider in NOTIFICATION_PROVIDERS
    ]
    projections = [
        projection
        for batch in batches
        for projection in batch.projections
    ]
    projections.sort(
        key=lambda projection: (
            projection.priority,
            projection.sort_at,
            projection.payload["key"],
        )
    )
    visible_projections = projections[:NOTIFICATION_ITEM_LIMIT]
    omitted_friend_request = any(
        projection.payload["kind"] == "FRIEND_REQUEST"
        for projection in projections[NOTIFICATION_ITEM_LIMIT:]
    )
    more_url = next((batch.more_url for batch in batches if batch.more_url), None)
    if omitted_friend_request:
        more_url = f"{reverse('social:friends')}?tab=requests"
    return {
        "version": NOTIFICATION_VERSION,
        "server_time": now.isoformat(),
        "incoming_count": sum(batch.incoming_count for batch in batches),
        "items": [projection.payload for projection in visible_projections],
        "more_url": more_url,
    }
