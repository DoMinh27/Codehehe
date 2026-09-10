from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from social.models import FriendRequest, Friendship, UserBlock, UserPresence
from social.services.friends import (
    SocialConflict,
    act_on_friend_request,
    block_user,
    heartbeat_presence,
    project_friend_presence,
    send_friend_request,
)
from social.services.notifications import get_notification_state


@override_settings(
    SOCIAL_FRIEND_REQUEST_TTL_SECONDS=2592000,
    SOCIAL_FRIEND_DECLINE_COOLDOWN_SECONDS=86400,
    SOCIAL_MAX_FRIENDS=100,
    SOCIAL_MAX_PENDING_SENT_REQUESTS=20,
    SOCIAL_FRIEND_REQUESTS_PER_HOUR=10,
    SOCIAL_PRESENCE_HEARTBEAT_SECONDS=30,
    SOCIAL_PRESENCE_TTL_SECONDS=90,
)
class FriendServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user(
            "alice", email="alice-private@example.com", password="pass"
        )
        self.bob = user_model.objects.create_user("bob", password="pass")
        self.cara = user_model.objects.create_user("cara", password="pass")

    def test_request_uses_canonical_pair_and_reverse_direction_does_not_auto_accept(self):
        invitation = send_friend_request(requester=self.bob, username="alice")

        self.assertEqual(invitation.user_low_id, min(self.alice.pk, self.bob.pk))
        self.assertEqual(invitation.user_high_id, max(self.alice.pk, self.bob.pk))
        with self.assertRaisesMessage(SocialConflict, "đang chờ phản hồi"):
            send_friend_request(requester=self.alice, username="bob")
        self.assertFalse(Friendship.objects.exists())

    def test_username_lookup_keeps_current_case_sensitive_identity_rule(self):
        with self.assertRaisesMessage(SocialConflict, "Không thể gửi"):
            send_friend_request(requester=self.alice, username="BOB")

    def test_accept_is_idempotent_and_creates_one_friendship(self):
        invitation = send_friend_request(requester=self.alice, username="bob")

        act_on_friend_request(actor=self.bob, request_id=invitation.pk, action="accept")
        act_on_friend_request(actor=self.bob, request_id=invitation.pk, action="accept")

        self.assertEqual(Friendship.objects.count(), 1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, FriendRequest.Status.ACCEPTED)

    def test_sender_cannot_accept_own_request(self):
        invitation = send_friend_request(requester=self.alice, username="bob")

        with self.assertRaisesMessage(SocialConflict, "không thể xử lý"):
            act_on_friend_request(actor=self.alice, request_id=invitation.pk, action="accept")

    def test_expired_request_releases_pair_for_new_request(self):
        invitation = send_friend_request(requester=self.alice, username="bob")
        after_expiry = invitation.expires_at + timedelta(seconds=1)

        replacement = send_friend_request(
            requester=self.bob,
            username="alice",
            now=after_expiry,
        )

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, FriendRequest.Status.CANCELLED)
        self.assertNotEqual(replacement.pk, invitation.pk)

    def test_declined_sender_observes_cooldown(self):
        invitation = send_friend_request(requester=self.alice, username="bob")
        act_on_friend_request(actor=self.bob, request_id=invitation.pk, action="decline")

        with self.assertRaisesMessage(SocialConflict, "cần chờ"):
            send_friend_request(requester=self.alice, username="bob")

    @override_settings(SOCIAL_FRIEND_REQUESTS_PER_HOUR=1)
    def test_send_rate_limit_is_calculated_from_server_records(self):
        send_friend_request(requester=self.alice, username="bob")

        with self.assertRaisesMessage(SocialConflict, "quá nhiều lời mời"):
            send_friend_request(requester=self.alice, username="cara")

    @override_settings(SOCIAL_MAX_PENDING_SENT_REQUESTS=1)
    def test_pending_sent_limit_is_enforced(self):
        send_friend_request(requester=self.alice, username="bob")

        with self.assertRaisesMessage(SocialConflict, "quá nhiều lời mời chờ"):
            send_friend_request(requester=self.alice, username="cara")

    def test_block_closes_relationship_requests_and_rematch(self):
        friendship = Friendship.objects.create(
            user_low_id=min(self.alice.pk, self.bob.pk),
            user_high_id=max(self.alice.pk, self.bob.pk),
        )
        invitation = FriendRequest.objects.create(
            user_low_id=min(self.alice.pk, self.cara.pk),
            user_high_id=max(self.alice.pk, self.cara.pk),
            requester=self.alice,
            expires_at=timezone.now() + timedelta(days=1),
        )
        match = Match.objects.create(
            room_code="SOC001",
            host=self.alice,
            status=Match.Status.FINISHED,
            ended_at=timezone.now(),
        )
        rematch = RematchRequest.objects.create(
            match=match,
            requester=self.alice,
            recipient=self.bob,
            expires_at=timezone.now() + timedelta(minutes=2),
        )

        block_user(actor=self.alice, other_user_id=self.bob.pk)

        self.assertFalse(Friendship.objects.filter(pk=friendship.pk).exists())
        self.assertTrue(UserBlock.objects.filter(blocker=self.alice, blocked=self.bob).exists())
        rematch.refresh_from_db()
        self.assertEqual(rematch.status, RematchRequest.Status.CANCELLED)
        self.assertEqual(invitation.status, FriendRequest.Status.PENDING)

    def test_database_rejects_noncanonical_friendship(self):
        high_id, low_id = max(self.alice.pk, self.bob.pk), min(self.alice.pk, self.bob.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Friendship.objects.create(user_low_id=high_id, user_high_id=low_id)


@override_settings(SOCIAL_PRESENCE_HEARTBEAT_SECONDS=30, SOCIAL_PRESENCE_TTL_SECONDS=90)
class PresenceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user("alice")
        self.bob = user_model.objects.create_user("bob")
        Friendship.objects.create(
            user_low_id=min(self.alice.pk, self.bob.pk),
            user_high_id=max(self.alice.pk, self.bob.pk),
        )

    def status_at(self, now):
        return project_friend_presence(user=self.alice, now=now)[0].status

    def test_presence_is_ready_before_ttl_and_inactive_at_boundary(self):
        now = timezone.now()
        UserPresence.objects.create(user=self.bob, last_seen_at=now - timedelta(seconds=89))
        self.assertEqual(self.status_at(now), "READY")

        UserPresence.objects.filter(user=self.bob).update(
            last_seen_at=now - timedelta(seconds=90)
        )
        self.assertEqual(self.status_at(now), "INACTIVE")

    def test_waiting_and_playing_match_take_precedence_without_battle_heartbeat(self):
        UserPresence.objects.create(user=self.bob, last_seen_at=timezone.now() - timedelta(hours=1))
        match = Match.objects.create(room_code="SOC002", host=self.bob)
        MatchPlayer.objects.create(match=match, user=self.bob, is_active=True, is_host=True)
        self.assertEqual(self.status_at(timezone.now()), "WAITING")

        match.status = Match.Status.PLAYING
        match.started_at = timezone.now()
        match.save(update_fields=["status", "started_at"])
        self.assertEqual(self.status_at(timezone.now()), "PLAYING")

    def test_hidden_presence_is_indistinguishable_from_inactive(self):
        UserPresence.objects.create(
            user=self.bob,
            last_seen_at=timezone.now(),
            show_presence_to_friends=False,
        )
        self.assertEqual(self.status_at(timezone.now()), "INACTIVE")

    def test_heartbeat_is_throttled_until_interval(self):
        now = timezone.now()
        first = heartbeat_presence(user=self.alice, now=now)
        heartbeat_presence(user=self.alice, now=now + timedelta(seconds=10))
        first.refresh_from_db()
        self.assertEqual(first.last_seen_at, now)

        heartbeat_presence(user=self.alice, now=now + timedelta(seconds=30))
        first.refresh_from_db()
        self.assertEqual(first.last_seen_at, now + timedelta(seconds=30))


class FriendViewsAndNotificationsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user(
            "alice", email="alice-private@example.com", password="pass"
        )
        self.bob = user_model.objects.create_user("bob", password="pass")
        self.client.force_login(self.alice)

    def test_friends_page_and_state_require_login(self):
        anonymous = Client()
        for url in (reverse("social:friends"), reverse("social:friends-state")):
            response = anonymous.get(url)
            self.assertEqual(response.status_code, 302)

    def test_authenticated_friends_page_renders_all_tabs_without_email(self):
        for tab in ("friends", "requests", "blocked"):
            response = self.client.get(reverse("social:friends"), {"tab": tab})
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.alice.email)

    def test_send_from_form_and_accept_from_json_notification(self):
        response = self.client.post(
            reverse("social:friend-request-send"),
            {"username": "bob"},
        )
        self.assertEqual(response.status_code, 302)
        invitation = FriendRequest.objects.get()

        self.client.force_login(self.bob)
        state = get_notification_state(user=self.bob)
        item = next(item for item in state["items"] if item["kind"] == "FRIEND_REQUEST")
        self.assertEqual(state["incoming_count"], 1)
        self.assertEqual(item["direction"], "INCOMING")
        self.assertNotIn("email", str(item).lower())

        response = self.client.post(
            reverse("social:friend-request-action", args=[invitation.pk]),
            data='{"action":"accept"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Friendship.objects.exists())

    def test_outgoing_request_does_not_increment_badge(self):
        send_friend_request(requester=self.alice, username="bob")
        state = get_notification_state(user=self.alice)
        self.assertEqual(state["incoming_count"], 0)
        self.assertEqual(state["items"][0]["direction"], "OUTGOING")

    def test_heartbeat_and_state_are_no_store(self):
        response = self.client.post(reverse("social:presence-heartbeat"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])

        response = self.client.get(reverse("social:friends-state"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_privacy_toggle_hides_presence(self):
        heartbeat_presence(user=self.alice)
        response = self.client.post(reverse("social:presence-privacy"), {})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserPresence.objects.get(user=self.alice).show_presence_to_friends)
