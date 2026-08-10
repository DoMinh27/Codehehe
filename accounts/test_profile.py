from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from matches.models import Match, MatchPlayer

from .models import PlayerActivityDay
from .services import get_current_activity_streak, get_player_profile_stats


User = get_user_model()


@override_settings(TIME_ZONE="Asia/Ho_Chi_Minh")
class PlayerProfileServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="profile-player")
        self.opponent = User.objects.create_user(username="profile-opponent")

    def finished_match(self, room_code, *, winner=None, is_draw=False):
        ended_at = datetime.now(tz=dt_timezone.utc)
        match = Match.objects.create(
            room_code=room_code,
            host=self.user,
            status=Match.Status.FINISHED,
            started_at=ended_at - timedelta(minutes=5),
            ended_at=ended_at,
            winner=winner,
            is_draw=is_draw,
            finish_reason=Match.FinishReason.TIMEOUT,
        )
        MatchPlayer.objects.create(match=match, user=self.user, slot=1)
        MatchPlayer.objects.create(match=match, user=self.opponent, slot=2)
        return match

    def test_profile_stats_count_only_finished_matches(self):
        self.finished_match("PROF01", winner=self.user)
        self.finished_match("PROF02", winner=self.opponent)
        self.finished_match("PROF03", is_draw=True)
        waiting = Match.objects.create(room_code="PROF04", host=self.user)
        MatchPlayer.objects.create(match=waiting, user=self.user, slot=1)

        stats = get_player_profile_stats(user=self.user)

        self.assertEqual(stats.total_matches, 3)
        self.assertEqual((stats.wins, stats.losses, stats.draws), (1, 1, 1))
        self.assertEqual(stats.win_rate, 33.3)

    def test_activity_streak_survives_until_end_of_next_day(self):
        today = date(2026, 8, 10)
        for offset in (1, 2, 3):
            activity_date = today - timedelta(days=offset)
            PlayerActivityDay.objects.create(
                user=self.user,
                activity_date=activity_date,
                first_activity_at=datetime.combine(
                    activity_date,
                    datetime.min.time(),
                    tzinfo=dt_timezone.utc,
                ),
            )

        self.assertEqual(
            get_current_activity_streak(user=self.user, today=today),
            3,
        )

    def test_activity_streak_is_zero_after_a_full_missed_day(self):
        today = date(2026, 8, 10)
        PlayerActivityDay.objects.create(
            user=self.user,
            activity_date=today - timedelta(days=2),
            first_activity_at=datetime.now(tz=dt_timezone.utc),
        )

        self.assertEqual(
            get_current_activity_streak(user=self.user, today=today),
            0,
        )


class PlayerProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="profile-viewer")

    def test_profile_requires_login(self):
        response = self.client.get(reverse("player-profile"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_profile_renders_private_user_stats(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("player-profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile.html")
        self.assertContains(response, self.user.username)
        self.assertContains(response, "0.0%")
        self.assertContains(response, reverse("match-history"))
