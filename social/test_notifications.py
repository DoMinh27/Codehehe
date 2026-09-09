from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from social.services.notifications import get_notification_state


User = get_user_model()


class NotificationFixtureMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            username="current", email="current@example.test", password="pass"
        )
        self.other = User.objects.create_user(
            username="opponent", email="opponent@example.test", password="pass"
        )

    def create_rematch(
        self,
        *,
        requester=None,
        recipient=None,
        created_at=None,
        expires_at=None,
        room_code="ABC123",
    ):
        requester = requester or self.other
        recipient = recipient or self.user
        now = timezone.now()
        match = Match.objects.create(
            room_code=room_code,
            host=requester,
            status=Match.Status.FINISHED,
            started_at=now - timedelta(minutes=5),
            ended_at=now,
        )
        MatchPlayer.objects.create(
            match=match,
            user=requester,
            score=2,
            slot=1,
            is_host=True,
            is_active=False,
        )
        MatchPlayer.objects.create(
            match=match,
            user=recipient,
            score=1,
            slot=2,
            is_active=False,
        )
        return RematchRequest.objects.create(
            match=match,
            requester=requester,
            recipient=recipient,
            created_at=created_at or now,
            expires_at=expires_at or now + timedelta(minutes=2),
        )


class NotificationProjectionTests(NotificationFixtureMixin, TestCase):
    def test_projects_incoming_and_outgoing_rematches_and_counts_only_incoming(self):
        now = timezone.now()
        incoming = self.create_rematch(
            created_at=now - timedelta(seconds=5),
            expires_at=now + timedelta(seconds=60),
        )
        third = User.objects.create_user(username="third", password="pass")
        outgoing = self.create_rematch(
            requester=self.user,
            recipient=third,
            created_at=now - timedelta(seconds=2),
            expires_at=now + timedelta(seconds=90),
            room_code="DEF456",
        )

        state = get_notification_state(user=self.user, now=now)

        self.assertEqual(state["version"], 1)
        self.assertEqual(state["incoming_count"], 1)
        self.assertEqual(
            [item["key"] for item in state["items"]],
            [f"REMATCH:{incoming.pk}", f"REMATCH:{outgoing.pk}"],
        )
        incoming_item, outgoing_item = state["items"]
        self.assertEqual(incoming_item["direction"], "INCOMING")
        self.assertEqual(incoming_item["actor"]["username"], "opponent")
        self.assertEqual(incoming_item["context"]["score"], "2 — 1")
        self.assertEqual(
            [action["code"] for action in incoming_item["actions"]],
            ["ACCEPT", "DECLINE"],
        )
        self.assertEqual(outgoing_item["direction"], "OUTGOING")
        self.assertEqual(outgoing_item["actor"]["username"], "third")
        self.assertEqual(
            [action["code"] for action in outgoing_item["actions"]], ["CANCEL"]
        )

    def test_omits_expired_and_processed_requests(self):
        now = timezone.now()
        self.create_rematch(
            created_at=now - timedelta(minutes=3),
            expires_at=now - timedelta(microseconds=1),
        )
        processed = self.create_rematch(room_code="DONE12")
        processed.status = RematchRequest.Status.DECLINED
        processed.responded_at = now
        processed.save(update_fields=["status", "responded_at"])

        state = get_notification_state(user=self.user, now=now)

        self.assertEqual(state["incoming_count"], 0)
        self.assertEqual(state["items"], [])

    def test_unavailable_incoming_request_can_only_be_declined(self):
        invitation = self.create_rematch()
        active_match = Match.objects.create(
            room_code="ACTIVE",
            host=self.other,
            status=Match.Status.WAITING,
        )
        MatchPlayer.objects.create(
            match=active_match,
            user=self.other,
            is_host=True,
            is_active=True,
        )

        item = get_notification_state(user=self.user)["items"][0]

        self.assertEqual(item["key"], f"REMATCH:{invitation.pk}")
        self.assertEqual(
            [action["code"] for action in item["actions"]], ["DECLINE"]
        )
        self.assertIn("phòng hoặc trận khác", item["unavailable_reason"])

    def test_caps_payload_but_keeps_exact_incoming_count(self):
        for index in range(21):
            opponent = User.objects.create_user(username=f"player{index}")
            self.create_rematch(
                requester=opponent,
                room_code=f"R{index:05d}",
                expires_at=timezone.now() + timedelta(minutes=5, seconds=index),
            )

        state = get_notification_state(user=self.user)

        self.assertEqual(state["incoming_count"], 21)
        self.assertEqual(len(state["items"]), 20)


class NotificationViewTests(NotificationFixtureMixin, TestCase):
    @override_settings(
        SOCIAL_NOTIFICATION_VISIBLE_POLL_SECONDS=7,
        SOCIAL_NOTIFICATION_HIDDEN_POLL_SECONDS=45,
    )
    def test_shell_is_visible_on_user_pages_but_not_during_battle(self):
        self.client.force_login(self.user)
        lobby_response = self.client.get(reverse("lobby"))
        self.assertContains(lobby_response, "data-notification-center")
        self.assertContains(lobby_response, 'data-visible-poll-seconds="7"')
        self.assertContains(lobby_response, 'data-hidden-poll-seconds="45"')

        match = Match.objects.create(
            room_code="BATTLE",
            host=self.user,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        MatchPlayer.objects.create(
            match=match,
            user=self.user,
            is_host=True,
            slot=1,
            is_active=True,
        )
        MatchPlayer.objects.create(
            match=match,
            user=self.other,
            slot=2,
            is_active=True,
        )

        response = self.client.get(reverse("battle", args=[match.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-notification-center")

    def test_requires_login_get_and_returns_private_payload(self):
        url = reverse("social:notification-state")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.create_rematch()
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["incoming_count"], 1)
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        rendered = response.content.decode()
        self.assertNotIn(self.user.email, rendered)
        self.assertNotIn("source_code", rendered)
