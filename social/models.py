import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Đang chờ"
        ACCEPTED = "ACCEPTED", "Đã đồng ý"
        DECLINED = "DECLINED", "Đã từ chối"
        CANCELLED = "CANCELLED", "Đã hủy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_requests_as_low",
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_requests_as_high",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_requests_sent",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user_low__lt=models.F("user_high")),
                name="friendrequest_canonical_pair",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(requester=models.F("user_low"))
                    | models.Q(requester=models.F("user_high"))
                ),
                name="friendrequest_requester_in_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="friendrequest_valid_expiry",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="PENDING", responded_at__isnull=True)
                    | (~models.Q(status="PENDING") & models.Q(responded_at__isnull=False))
                ),
                name="friendrequest_response_state",
            ),
            models.UniqueConstraint(
                fields=["user_low", "user_high"],
                condition=models.Q(status="PENDING"),
                name="friendrequest_one_pending_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["requester", "status", "created_at"],
                name="friendreq_sender_state_idx",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="friendreq_state_expiry_idx",
            ),
        ]

    @property
    def recipient_id(self):
        return self.user_high_id if self.requester_id == self.user_low_id else self.user_low_id

    @property
    def recipient(self):
        return self.user_high if self.requester_id == self.user_low_id else self.user_low

    def __str__(self):
        return f"{self.requester} → {self.recipient} · {self.status}"


class Friendship(models.Model):
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_low",
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_high",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user_low__lt=models.F("user_high")),
                name="friendship_canonical_pair",
            ),
            models.UniqueConstraint(
                fields=["user_low", "user_high"],
                name="friendship_unique_pair",
            ),
        ]

    def other_user(self, user):
        return self.user_high if user.pk == self.user_low_id else self.user_low

    def __str__(self):
        return f"{self.user_low} ↔ {self.user_high}"


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_blocks_created",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="userblock_distinct_users",
            ),
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="userblock_unique_direction",
            ),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class UserPresence(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_presence",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    show_presence_to_friends = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self):
        return f"Presence · {self.user}"


class DirectMatchInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Đang chờ"
        ACCEPTED = "ACCEPTED", "Đã đồng ý"
        DECLINED = "DECLINED", "Đã từ chối"
        CANCELLED = "CANCELLED", "Đã hủy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="direct_match_invitations_sent",
    )
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="direct_match_invitations_received",
    )
    # Internal canonical key makes reverse-direction requests share one pending slot.
    pair_key = models.CharField(max_length=64, editable=False)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    new_match = models.OneToOneField(
        "matches.Match",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="direct_invitation_origin",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(inviter=models.F("invitee")),
                name="directinvite_distinct_users",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="directinvite_valid_expiry",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="PENDING", responded_at__isnull=True)
                    | (~models.Q(status="PENDING") & models.Q(responded_at__isnull=False))
                ),
                name="directinvite_response_state",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="ACCEPTED", new_match__isnull=False)
                    | (~models.Q(status="ACCEPTED") & models.Q(new_match__isnull=True))
                ),
                name="directinvite_accepted_match",
            ),
            models.UniqueConstraint(
                fields=["pair_key"],
                condition=models.Q(status="PENDING"),
                name="directinvite_one_pending_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["invitee", "status", "expires_at"],
                name="directinvite_recipient_idx",
            ),
            models.Index(
                fields=["inviter", "created_at"],
                name="directinvite_sender_idx",
            ),
        ]

    @staticmethod
    def make_pair_key(first_id, second_id):
        low_id, high_id = sorted((first_id, second_id))
        return f"{low_id}:{high_id}"

    def save(self, *args, **kwargs):
        if self.inviter_id and self.invitee_id:
            self.pair_key = self.make_pair_key(self.inviter_id, self.invitee_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Match invite {self.inviter} → {self.invitee} · {self.status}"
