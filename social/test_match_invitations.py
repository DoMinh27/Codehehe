import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import OperationalError, close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from matches.services.room import CreateRoomService
from social.models import DirectMatchInvitation, Friendship, UserPresence
from social.services.match_invitations import (
    MatchInvitationError,
    MatchInvitationService,
    invitation_result,
    send_match_invitation,
)
from social.services.notifications import get_notification_state


TEST_SETTINGS = {
    "SOCIAL_PRESENCE_HEARTBEAT_SECONDS": 30,
    "SOCIAL_PRESENCE_TTL_SECONDS": 90,
    "SOCIAL_MATCH_INVITE_TTL_SECONDS": 120,
    "SOCIAL_MAX_PENDING_MATCH_INVITES": 3,
    "SOCIAL_MATCH_INVITES_PER_10_MINUTES": 5,
}


class MatchInvitationFixtureMixin:
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user("alice", password="pass")
        self.bob = user_model.objects.create_user("bob", password="pass")
        self.cara = user_model.objects.create_user("cara", password="pass")
        self.make_friends(self.alice, self.bob)
        self.make_friends(self.alice, self.cara)
        self.set_ready(self.alice, self.bob, self.cara)

    @staticmethod
    def make_friends(first, second):
        Friendship.objects.create(
            user_low_id=min(first.pk, second.pk),
            user_high_id=max(first.pk, second.pk),
        )

    @staticmethod
    def set_ready(*users, now=None):
        now = now or timezone.now()
        for user in users:
            UserPresence.objects.update_or_create(
                user=user,
                defaults={"last_seen_at": now, "show_presence_to_friends": True},
            )

    def service(self, code="DUEL01"):
        return MatchInvitationService(
            room_service=CreateRoomService(code_generator=lambda: code)
        )


@override_settings(**TEST_SETTINGS)
class MatchInvitationServiceTests(MatchInvitationFixtureMixin, TestCase):
    def test_send_requires_friendship_and_both_players_ready(self):
        Friendship.objects.filter(
            user_low_id=min(self.alice.pk, self.bob.pk),
            user_high_id=max(self.alice.pk, self.bob.pk),
        ).delete()
        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        self.assertEqual(error.exception.code, "RECIPIENT_UNAVAILABLE")

        self.make_friends(self.alice, self.bob)
        UserPresence.objects.filter(user=self.bob).update(
            last_seen_at=timezone.now() - timedelta(seconds=90)
        )
        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        self.assertEqual(error.exception.code, "PLAYERS_UNAVAILABLE")
        self.assertFalse(DirectMatchInvitation.objects.exists())

    def test_send_reserves_no_room_and_reverse_request_does_not_duplicate(self):
        now = timezone.now()
        invitation = send_match_invitation(
            inviter=self.alice,
            invitee_id=self.bob.pk,
            now=now,
        )
        self.assertEqual(invitation.expires_at - invitation.created_at, timedelta(seconds=120))
        self.assertFalse(Match.objects.exists())

        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.bob, invitee_id=self.alice.pk)
        self.assertEqual(error.exception.code, "INVITATION_PENDING")
        self.assertEqual(DirectMatchInvitation.objects.count(), 1)

    @override_settings(SOCIAL_MAX_PENDING_MATCH_INVITES=1)
    def test_pending_limits_apply_to_outgoing_and_incoming(self):
        send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.alice, invitee_id=self.cara.pk)
        self.assertEqual(error.exception.code, "OUTGOING_LIMIT")

        self.make_friends(self.bob, self.cara)
        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.cara, invitee_id=self.bob.pk)
        self.assertEqual(error.exception.code, "INCOMING_LIMIT")

    @override_settings(SOCIAL_MATCH_INVITES_PER_10_MINUTES=1)
    def test_send_rate_limit_uses_server_records(self):
        first = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        self.service().act(actor=self.alice, invitation_id=first.pk, action="cancel")
        with self.assertRaises(MatchInvitationError) as error:
            send_match_invitation(inviter=self.alice, invitee_id=self.cara.pk)
        self.assertEqual(error.exception.code, "RATE_LIMITED")

    def test_accept_creates_one_classic_room_and_replay_returns_it(self):
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        service = self.service()

        accepted = service.act(
            actor=self.bob,
            invitation_id=invitation.pk,
            action="accept",
        )
        replay = service.act(
            actor=self.bob,
            invitation_id=invitation.pk,
            action="accept",
        )

        self.assertEqual(accepted.new_match_id, replay.new_match_id)
        match = accepted.new_match
        self.assertEqual(match.host, self.alice)
        self.assertEqual(match.status, Match.Status.WAITING)
        self.assertEqual(match.players.count(), 2)
        self.assertEqual(match.players.filter(is_active=True).count(), 2)
        self.assertEqual(Match.objects.count(), 1)

    def test_accept_closes_other_direct_and_rematch_invitations(self):
        accepted = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        other = send_match_invitation(inviter=self.alice, invitee_id=self.cara.pk)
        old_match = Match.objects.create(
            room_code="OLD001",
            host=self.alice,
            status=Match.Status.FINISHED,
            ended_at=timezone.now(),
        )
        rematch = RematchRequest.objects.create(
            match=old_match,
            requester=self.alice,
            recipient=self.cara,
            expires_at=timezone.now() + timedelta(minutes=2),
        )

        self.service().act(actor=self.bob, invitation_id=accepted.pk, action="accept")

        other.refresh_from_db()
        rematch.refresh_from_db()
        self.assertEqual(other.status, DirectMatchInvitation.Status.CANCELLED)
        self.assertEqual(rematch.status, RematchRequest.Status.CANCELLED)

    def test_only_invitee_can_accept_and_inviter_can_cancel(self):
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        with self.assertRaises(MatchInvitationError) as error:
            self.service().act(
                actor=self.alice,
                invitation_id=invitation.pk,
                action="accept",
            )
        self.assertEqual(error.exception.status, 403)

        cancelled = self.service().act(
            actor=self.alice,
            invitation_id=invitation.pk,
            action="cancel",
        )
        self.assertEqual(cancelled.status, DirectMatchInvitation.Status.CANCELLED)

    def test_accept_rechecks_presence_and_active_membership(self):
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        busy_match = Match.objects.create(
            room_code="BUSY01",
            host=self.bob,
            status=Match.Status.WAITING,
        )
        MatchPlayer.objects.create(
            match=busy_match,
            user=self.bob,
            is_host=True,
            slot=1,
            is_active=True,
        )

        with self.assertRaises(MatchInvitationError) as error:
            self.service().act(
                actor=self.bob,
                invitation_id=invitation.pk,
                action="accept",
            )

        self.assertEqual(error.exception.code, "PLAYERS_UNAVAILABLE")
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, DirectMatchInvitation.Status.PENDING)
        self.assertEqual(Match.objects.count(), 1)

    def test_expired_invitation_cannot_create_room(self):
        now = timezone.now()
        invitation = send_match_invitation(
            inviter=self.alice,
            invitee_id=self.bob.pk,
            now=now,
        )
        with self.assertRaises(MatchInvitationError) as error:
            self.service().act(
                actor=self.bob,
                invitation_id=invitation.pk,
                action="accept",
                now=invitation.expires_at,
            )
        self.assertEqual(error.exception.code, "INVITATION_EXPIRED")
        self.assertFalse(Match.objects.exists())

    def test_notification_counts_only_incoming_and_accept_points_to_waiting_room(self):
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        sender_state = get_notification_state(user=self.alice)
        recipient_state = get_notification_state(user=self.bob)

        self.assertEqual(sender_state["incoming_count"], 0)
        self.assertEqual(recipient_state["incoming_count"], 1)
        item = recipient_state["items"][0]
        self.assertEqual(item["kind"], "MATCH_INVITE")
        self.assertEqual([action["code"] for action in item["actions"]], ["ACCEPT", "DECLINE"])

        accepted = self.service().act(
            actor=self.bob,
            invitation_id=invitation.pk,
            action="accept",
        )
        self.assertEqual(
            reverse("waiting-room", args=[accepted.new_match.room_code]),
            invitation_result(accepted)["room_url"],
        )


@override_settings(**TEST_SETTINGS)
class MatchInvitationApiTests(MatchInvitationFixtureMixin, TestCase):
    def test_lobby_and_friends_page_offer_ready_friend_challenge(self):
        self.client.force_login(self.alice)
        for url in (reverse("lobby"), reverse("social:friends")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Mời đấu")
            self.assertNotContains(response, "alice-private@example.com")

    def test_send_and_action_require_login_csrf_and_return_no_store(self):
        send_url = reverse("social:match-invitation-send")
        anonymous = Client()
        self.assertEqual(anonymous.post(send_url).status_code, 302)

        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.alice)
        self.assertEqual(
            secure.post(
                send_url,
                data=json.dumps({"recipient_id": self.bob.pk}),
                content_type="application/json",
            ).status_code,
            403,
        )

        self.client.force_login(self.alice)
        response = self.client.post(
            send_url,
            data=json.dumps({"recipient_id": self.bob.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        invitation = DirectMatchInvitation.objects.get()

        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("social:match-invitation-action", args=[invitation.pk]),
            data=json.dumps({"action": "accept"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["room_url"].endswith("/"))
        self.assertIn("no-store", response["Cache-Control"])

    def test_staff_has_no_player_api_bypass(self):
        staff = get_user_model().objects.create_user("staff", is_staff=True)
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)
        self.client.force_login(staff)
        response = self.client.post(
            reverse("social:match-invitation-action", args=[invitation.pk]),
            data=json.dumps({"action": "accept"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


@override_settings(**TEST_SETTINGS)
class MatchInvitationConcurrencyTests(MatchInvitationFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def race(self, operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            except (MatchInvitationError, OperationalError) as error:
                return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_accept_replay_race_creates_only_one_room(self):
        invitation = send_match_invitation(inviter=self.alice, invitee_id=self.bob.pk)

        results = self.race(
            [
                lambda: self.service("RACE01").act(
                    actor=get_user_model().objects.get(pk=self.bob.pk),
                    invitation_id=invitation.pk,
                    action="accept",
                ),
                lambda: self.service("RACE01").act(
                    actor=get_user_model().objects.get(pk=self.bob.pk),
                    invitation_id=invitation.pk,
                    action="accept",
                ),
            ]
        )

        self.assertTrue(
            any(
                isinstance(result, DirectMatchInvitation)
                and result.status == DirectMatchInvitation.Status.ACCEPTED
                for result in results
            ),
            repr(results),
        )
        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(MatchPlayer.objects.filter(is_active=True).count(), 2)
