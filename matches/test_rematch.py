import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchPlayer, RematchRequest
from matches.rules import current_match_rules
from matches.services.rematch import RematchError, RematchService, get_rematch_state
from matches.services.room import (
    CreateRoomService,
    JoinRoomService,
    LeaveRoomService,
    RoomError,
)


class RematchFixtureMixin:
    def setUp(self):
        self.host = get_user_model().objects.create_user(username="host")
        self.guest = get_user_model().objects.create_user(username="guest")
        self.staff = get_user_model().objects.create_user(
            username="staff", is_staff=True
        )
        self.match = Match.objects.create(
            room_code="SOURCE",
            host=self.host,
            status=Match.Status.FINISHED,
            started_at=timezone.now() - timedelta(minutes=5),
            ended_at=timezone.now(),
            winner=self.guest,
            finish_reason=Match.FinishReason.SURRENDER,
            surrendered_by=self.host,
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match, user=self.host, slot=1, is_host=True
        )
        self.guest_player = MatchPlayer.objects.create(
            match=self.match, user=self.guest, slot=2
        )
        self.service = RematchService(
            room_service=CreateRoomService(code_generator=lambda: "REM001")
        )

    def act(self, action, user=None):
        return self.service.act(
            user=user or self.host, match_id=self.match.pk, action=action
        )

    def state(self, user=None):
        return get_rematch_state(user=user or self.host, match_id=self.match.pk)


class RematchServiceTests(RematchFixtureMixin, TestCase):
    def test_request_creates_no_room_and_accept_is_idempotent(self):
        state = self.act("request", self.guest)
        self.assertEqual(state["status"], "PENDING")
        self.assertEqual(Match.objects.count(), 1)
        invitation = RematchRequest.objects.get(match=self.match)
        self.assertEqual(
            invitation.expires_at - invitation.created_at, timedelta(seconds=120)
        )
        accepted = self.act("accept", self.host)
        replay = self.act("accept", self.host)
        self.assertEqual(replay["status"], accepted["status"])
        self.assertEqual(replay["room_url"], accepted["room_url"])
        invitation.refresh_from_db()
        match = invitation.new_match
        self.assertEqual(match.status, Match.Status.WAITING)
        self.assertEqual(match.host_id, self.guest.pk)
        self.assertEqual(match.players.count(), 2)
        self.assertEqual(
            set(match.players.values_list("user_id", flat=True)),
            {self.host.pk, self.guest.pk},
        )
        self.assertEqual(match.players.filter(is_active=True).count(), 2)
        self.assertEqual(Match.objects.count(), 2)
        self.assertEqual(match.rules_snapshot, current_match_rules().to_snapshot())
        self.assertEqual(match.timeline_version, 0)
        self.assertEqual(
            list(match.players.values_list("score", "energy", "time_penalty_seconds")),
            [(0, 0, 0), (0, 0, 0)],
        )
        self.assertFalse(match.match_problems.exists())
        self.assertFalse(match.submissions.exists())
        self.assertFalse(match.skill_uses.exists())

    def test_opposing_request_does_not_accept_or_extend_the_invitation(self):
        self.act("request")
        invitation = RematchRequest.objects.get(match=self.match)
        other = self.act("request", self.guest)
        invitation.refresh_from_db()
        self.assertFalse(other["is_requester"])
        self.assertEqual(other["actions"], ["accept", "decline"])
        self.assertEqual(invitation.status, "PENDING")
        self.assertEqual(RematchRequest.objects.count(), 1)
        self.assertEqual(Match.objects.count(), 1)

    def test_decline_cancel_expiry_are_terminal_with_no_second_request(self):
        for action, status, user in (
            ("decline", "DECLINED", self.guest),
            ("cancel", "CANCELLED", self.host),
        ):
            with self.subTest(action=action), transaction.atomic():
                self.act("request")
                self.assertEqual(self.act(action, user)["status"], status)
                self.assertEqual(self.act(action, user)["status"], status)
                self.assertEqual(self.act("request")["status"], status)
                self.assertEqual(RematchRequest.objects.count(), 1)
                transaction.set_rollback(True)
        self.act("request")
        invitation = RematchRequest.objects.get(match=self.match)
        with patch(
            "matches.services.rematch.timezone.now", return_value=invitation.expires_at
        ):
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.state()["status"], "EXPIRED")
            self.assertFalse(
                any(
                    q["sql"].lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE"))
                    for q in queries
                )
            )
            with self.assertRaises(RematchError):
                self.act("accept", self.guest)
            self.assertEqual(self.act("request")["status"], "EXPIRED")
        self.assertEqual(Match.objects.count(), 1)

    def test_busy_player_rejects_without_reserving_a_room(self):
        other_room = CreateRoomService(code_generator=lambda: "BUSY01").create(
            user=self.guest
        )
        with self.assertRaises(RematchError) as error:
            self.act("request")
        self.assertEqual(error.exception.code, "REMATCH_PLAYER_UNAVAILABLE")
        self.assertFalse(RematchRequest.objects.exists())
        state = self.state()
        self.assertEqual(state["actions"], [])
        self.assertNotIn(other_room.room_code, json.dumps(state))

    def test_player_joins_another_room_between_request_and_accept(self):
        self.act("request")
        room = CreateRoomService(code_generator=lambda: "BUSY02").create(user=self.host)
        with self.assertRaises(RematchError):
            self.act("accept", self.guest)
        self.assertEqual(RematchRequest.objects.get(match=self.match).status, "PENDING")
        self.assertEqual(Match.objects.count(), 2)
        LeaveRoomService().leave(user=self.host, room_code=room.room_code)
        self.assertEqual(self.act("accept", self.guest)["status"], "ACCEPTED")

    def test_failure_adding_second_member_rolls_back_the_whole_room(self):
        self.act("request")
        original = MatchPlayer.objects.create

        def fail_guest(**kwargs):
            if kwargs.get("slot") == 2:
                raise IntegrityError("simulated active membership race")
            return original(**kwargs)

        with patch(
            "matches.services.rematch.MatchPlayer.objects.create",
            side_effect=fail_guest,
        ):
            with self.assertRaises(RematchError):
                self.act("accept", self.guest)
        self.assertEqual(Match.objects.count(), 1)
        self.assertFalse(MatchPlayer.objects.filter(is_active=True).exists())
        self.assertEqual(RematchRequest.objects.get(match=self.match).status, "PENDING")
        self.assertEqual(self.act("accept", self.guest)["status"], "ACCEPTED")

    def test_room_code_collision_retries_inside_the_acceptance_transaction(self):
        codes = iter(["SOURCE", "NEW123"])
        self.service.room_service.code_generator = lambda: next(codes)
        self.act("request")
        self.assertEqual(self.act("accept", self.guest)["status"], "ACCEPTED")
        self.assertEqual(RematchRequest.objects.get().new_match.room_code, "NEW123")
        self.assertEqual(Match.objects.count(), 2)

    def test_link_tracks_new_match_status_and_membership(self):
        self.act("request")
        self.act("accept", self.guest)
        new = RematchRequest.objects.get().new_match
        self.assertEqual(
            self.state()["room_url"], reverse("waiting-room", args=[new.room_code])
        )
        for status, route in (("PLAYING", "battle"), ("FINISHED", "match-result")):
            new.status = status
            new.save(update_fields=["status"])
            self.assertEqual(self.state()["room_url"], reverse(route, args=[new.pk]))
        new.status = "WAITING"
        new.save(update_fields=["status"])
        LeaveRoomService().leave(user=self.guest, room_code=new.room_code)
        self.assertIsNone(self.state(self.guest)["room_url"])
        LeaveRoomService().leave(user=self.host, room_code=new.room_code)
        self.assertIsNone(self.state()["room_url"])
        self.assertEqual(self.act("request")["status"], "ACCEPTED")
        self.assertEqual(Match.objects.count(), 2)

    def test_only_right_participant_can_respond(self):
        for status in ("WAITING", "PLAYING", "CANCELLED"):
            self.match.status = status
            self.match.save(update_fields=["status"])
            with self.assertRaises(RematchError):
                self.act("request")
        self.match.status = "FINISHED"
        self.match.save(update_fields=["status"])
        with self.assertRaises(RematchError) as error:
            self.act("request", self.staff)
        self.assertEqual(error.exception.status, 403)
        self.act("request")
        for action, user in (
            ("accept", self.host),
            ("decline", self.host),
            ("cancel", self.guest),
        ):
            with self.assertRaises(RematchError):
                self.act(action, user)

    def test_sqlite_capacity_trigger_and_active_membership_remain(self):
        self.act("request")
        self.act("accept", self.guest)
        new = RematchRequest.objects.get().new_match
        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(match=new, user=self.staff)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchPlayer.objects.create(match=self.match, user=self.host, is_active=True)


class RematchApiTests(RematchFixtureMixin, TestCase):
    def test_permissions_methods_csrf_and_validation(self):
        state_url = reverse("rematch-state", args=[self.match.pk])
        action_url = reverse("rematch-action", args=[self.match.pk])
        self.assertEqual(self.client.get(state_url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(state_url).status_code, 403)
        self.client.force_login(self.host)
        self.assertEqual(self.client.get(action_url).status_code, 405)
        self.assertEqual(self.client.post(state_url).status_code, 405)
        self.assertEqual(
            self.client.get(reverse("rematch-state", args=[999999])).status_code, 404
        )
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.host)
        self.assertEqual(
            secure_client.post(
                action_url, {"action": "request"}, content_type="application/json"
            ).status_code,
            403,
        )
        for payload in ("broken", "[]", '{"action": []}', '{"action": "unknown"}'):
            response = self.client.post(
                action_url, data=payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("no-store", response.headers["Cache-Control"])
        response = self.client.post(
            action_url, {"action": "request"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("no-store", self.client.get(state_url).headers["Cache-Control"])

    @override_settings(AI_REVIEW_ENABLED=False)
    def test_result_bootstraps_rematch_without_ai_and_hides_controls_from_staff(self):
        url = reverse("match-result", args=[self.match.pk])
        self.client.force_login(self.host)
        response = self.client.get(url)
        self.assertContains(response, 'id="rematch-controls"')
        self.assertContains(response, "result-main.bundle.js")
        self.assertNotContains(response, 'id="ai-review-config"')
        self.assertNotContains(response, "const activeStateUrl")
        self.assertEqual(
            response.context["rematch_config"]["initialState"]["status"], "NONE"
        )
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(url), 'id="rematch-controls"')


class RematchConcurrencyTests(RematchFixtureMixin, TransactionTestCase):
    def race(self, operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            except (RematchError, RoomError, OperationalError) as error:
                return error
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_simultaneous_invites_and_accepts_never_duplicate_rooms(self):
        results = self.race(
            [lambda: self.act("request"), lambda: self.act("request", self.guest)]
        )
        self.assertTrue(any(isinstance(r, dict) for r in results))
        self.assertEqual(RematchRequest.objects.count(), 1)
        invitation = RematchRequest.objects.get()
        recipient = get_user_model().objects.get(pk=invitation.recipient_id)
        results = self.race(
            [
                lambda: self.act("accept", recipient),
                lambda: self.act("accept", recipient),
            ]
        )
        self.assertTrue(
            any(isinstance(r, dict) and r["status"] == "ACCEPTED" for r in results),
            repr(results),
        )
        self.assertEqual(Match.objects.count(), 2)
        self.assertEqual(MatchPlayer.objects.filter(is_active=True).count(), 2)

    def test_accept_racing_with_join_preserves_single_active_membership(self):
        self.act("request")
        room = CreateRoomService(code_generator=lambda: "RACE01").create(
            user=self.staff
        )
        self.race(
            [
                lambda: self.act("accept", self.guest),
                lambda: JoinRoomService().join(
                    user=self.host, room_code=room.room_code
                ),
            ]
        )
        self.assertEqual(
            MatchPlayer.objects.filter(user=self.host, is_active=True).count(), 1
        )
        invitation = RematchRequest.objects.get()
        if invitation.status == "ACCEPTED":
            self.assertEqual(invitation.new_match.players.count(), 2)
        else:
            self.assertEqual(invitation.status, "PENDING")
            self.assertIsNone(invitation.new_match_id)
            self.assertEqual(Match.objects.count(), 2)
