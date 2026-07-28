from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Match, MatchPlayer
from .services.room import (
    ActiveMatchExistsError,
    AlreadyJoinedError,
    CreateRoomService,
    InvalidRoomCodeError,
    JoinRoomService,
    LeaveRoomService,
    RoomFullError,
    RoomNotFoundError,
    RoomNotWaitingError,
)

User = get_user_model()


class RoomServiceTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.second = User.objects.create_user(
            username="second", password="Password-938!"
        )
        self.third = User.objects.create_user(username="third", password="Password-938!")

    def test_create_room_assigns_six_character_code_and_host(self):
        match = CreateRoomService(code_generator=lambda: "AB12CD").create(user=self.host)

        self.assertEqual(match.room_code, "AB12CD")
        self.assertEqual(match.status, Match.Status.WAITING)
        self.assertTrue(
            MatchPlayer.objects.filter(
                match=match,
                user=self.host,
                is_host=True,
            ).exists()
        )

    def test_create_room_retries_after_code_collision(self):
        Match.objects.create(room_code="ABC123", host=self.host)
        room_codes = iter(["ABC123", "NEW456"])

        match = CreateRoomService(code_generator=lambda: next(room_codes)).create(
            user=self.host
        )

        self.assertEqual(match.room_code, "NEW456")
        self.assertEqual(MatchPlayer.objects.filter(match=match).count(), 1)

    def test_user_cannot_create_or_join_a_second_active_match(self):
        active_match = CreateRoomService(code_generator=lambda: "FIRST1").create(
            user=self.host
        )
        other_match = CreateRoomService(code_generator=lambda: "OTHER1").create(
            user=self.second
        )

        with self.assertRaises(ActiveMatchExistsError) as create_error:
            CreateRoomService(code_generator=lambda: "SECOND").create(user=self.host)
        with self.assertRaises(ActiveMatchExistsError) as join_error:
            JoinRoomService().join(user=self.host, room_code=other_match.room_code)

        self.assertEqual(create_error.exception.match, active_match)
        self.assertEqual(join_error.exception.match, active_match)

    def test_join_normalizes_code_and_creates_non_host_player(self):
        match = CreateRoomService(code_generator=lambda: "JOIN01").create(user=self.host)

        player = JoinRoomService().join(user=self.second, room_code=" join01 ")

        self.assertEqual(player.match, match)
        self.assertFalse(player.is_host)
        self.assertEqual(match.players.count(), 2)

    def test_join_rejects_invalid_or_unknown_code(self):
        with self.assertRaises(InvalidRoomCodeError):
            JoinRoomService().join(user=self.second, room_code="bad!")
        with self.assertRaises(RoomNotFoundError):
            JoinRoomService().join(user=self.second, room_code="NONE00")

    def test_join_rejects_duplicate_player(self):
        match = CreateRoomService(code_generator=lambda: "DUPL01").create(user=self.host)

        with self.assertRaises(AlreadyJoinedError):
            JoinRoomService().join(user=self.host, room_code=match.room_code)

        self.assertEqual(match.players.count(), 1)

    def test_join_rejects_room_that_is_not_waiting(self):
        match = CreateRoomService(code_generator=lambda: "PLAY01").create(user=self.host)
        match.status = Match.Status.PLAYING
        match.save()

        with self.assertRaises(RoomNotWaitingError):
            JoinRoomService().join(user=self.second, room_code=match.room_code)

    def test_join_rejects_third_player_without_creating_record(self):
        match = CreateRoomService(code_generator=lambda: "FULL01").create(user=self.host)
        JoinRoomService().join(user=self.second, room_code=match.room_code)

        with self.assertRaises(RoomFullError):
            JoinRoomService().join(user=self.third, room_code=match.room_code)

        self.assertEqual(match.players.count(), 2)
        self.assertFalse(MatchPlayer.objects.filter(match=match, user=self.third).exists())

    def test_guest_can_leave_and_host_leave_cancels_room(self):
        match = CreateRoomService(code_generator=lambda: "LEAVE1").create(user=self.host)
        JoinRoomService().join(user=self.second, room_code=match.room_code)

        LeaveRoomService().leave(user=self.second, room_code=match.room_code)
        self.assertFalse(match.players.filter(user=self.second).exists())

        JoinRoomService().join(user=self.second, room_code=match.room_code)
        LeaveRoomService().leave(user=self.host, room_code=match.room_code)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.CANCELLED)
        self.assertFalse(match.players.filter(is_active=True).exists())


class RoomViewTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.second = User.objects.create_user(
            username="second", password="Password-938!"
        )
        self.outsider = User.objects.create_user(
            username="outsider", password="Password-938!"
        )
        self.match = CreateRoomService(code_generator=lambda: "ROOM01").create(
            user=self.host
        )

    def test_room_routes_require_login(self):
        urls = [
            reverse("room-create"),
            reverse("room-join"),
            reverse("waiting-room", kwargs={"room_code": self.match.room_code}),
            reverse("waiting-room-state", kwargs={"room_code": self.match.room_code}),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)

    def test_create_room_resumes_existing_active_room(self):
        self.client.force_login(self.host)

        response = self.client.post(reverse("room-create"))

        self.assertRedirects(
            response,
            reverse("waiting-room", kwargs={"room_code": self.match.room_code}),
        )
        self.assertEqual(Match.objects.filter(host=self.host).count(), 1)

    def test_join_redirects_player_to_waiting_room(self):
        self.client.force_login(self.second)

        response = self.client.post(
            reverse("room-join"),
            {"room_code": " room01 "},
        )

        self.assertRedirects(
            response,
            reverse("waiting-room", kwargs={"room_code": self.match.room_code}),
        )
        self.assertTrue(self.match.players.filter(user=self.second).exists())

    def test_third_player_sees_room_full_message(self):
        JoinRoomService().join(user=self.second, room_code=self.match.room_code)
        self.client.force_login(self.outsider)

        response = self.client.post(
            reverse("room-join"),
            {"room_code": self.match.room_code},
            follow=True,
        )

        self.assertRedirects(response, reverse("lobby"))
        self.assertContains(response, "Phòng đã đầy.")
        self.assertEqual(self.match.players.count(), 2)

    def test_only_members_can_view_waiting_room_and_state(self):
        waiting_url = reverse(
            "waiting-room", kwargs={"room_code": self.match.room_code}
        )
        state_url = reverse(
            "waiting-room-state", kwargs={"room_code": self.match.room_code}
        )
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(waiting_url).status_code, 403)
        self.assertEqual(self.client.get(state_url).status_code, 403)

    def test_waiting_room_renders_polling_and_disabled_start_for_host(self):
        self.client.force_login(self.host)

        response = self.client.get(
            reverse("waiting-room", kwargs={"room_code": self.match.room_code})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/waiting_room.html")
        self.assertContains(response, self.match.room_code)
        self.assertContains(response, "window.setTimeout(")
        self.assertContains(response, "Bắt đầu trận")
        self.assertContains(response, "disabled")

    def test_state_returns_two_slots_and_reflects_joined_player(self):
        JoinRoomService().join(user=self.second, room_code=self.match.room_code)
        self.client.force_login(self.host)

        response = self.client.get(
            reverse(
                "waiting-room-state",
                kwargs={"room_code": self.match.room_code},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "room_code": self.match.room_code,
                "status": Match.Status.WAITING,
                "host": self.host.username,
                "players": [
                    {"username": self.host.username, "is_host": True},
                    {"username": self.second.username, "is_host": False},
                ],
                "is_full": True,
                "can_start": True,
                "battle_url": None,
                "lobby_url": None,
            },
        )

    def test_lobby_resumes_waiting_then_playing_match(self):
        self.client.force_login(self.host)

        response = self.client.get(reverse("lobby"))
        self.assertRedirects(
            response,
            reverse("waiting-room", kwargs={"room_code": self.match.room_code}),
        )

        self.match.status = Match.Status.PLAYING
        self.match.save(update_fields=["status"])
        response = self.client.get(reverse("lobby"))
        self.assertRedirects(response, reverse("battle", args=[self.match.pk]))

    def test_active_match_state_supports_global_resume(self):
        self.client.force_login(self.host)
        url = reverse("active-match-state")

        waiting = self.client.get(url)
        self.assertEqual(
            waiting.json(),
            {
                "active": True,
                "status": Match.Status.WAITING,
                "url": reverse(
                    "waiting-room",
                    kwargs={"room_code": self.match.room_code},
                ),
            },
        )

        self.match.status = Match.Status.PLAYING
        self.match.save(update_fields=["status"])
        playing = self.client.get(url)
        self.assertEqual(playing.json()["url"], reverse("battle", args=[self.match.pk]))

    def test_leave_room_endpoint_requires_post_and_releases_guest(self):
        JoinRoomService().join(user=self.second, room_code=self.match.room_code)
        self.client.force_login(self.second)
        url = reverse("room-leave", kwargs={"room_code": self.match.room_code})

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)

        self.assertRedirects(response, reverse("lobby"))
        self.assertFalse(self.match.players.filter(user=self.second).exists())

    def test_room_creation_keeps_csrf_protection(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.host)

        response = csrf_client.post(reverse("room-create"))

        self.assertEqual(response.status_code, 403)
