from datetime import timedelta
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matches.integrity import IntegrityPolicy, current_integrity_policy
from matches.models import (
    Match,
    MatchIntegrityEvent,
    MatchIntegrityState,
    MatchPlayer,
)
from matches.services.integrity import MatchIntegrityService, finalize_match_integrity
from matches.services.gameplay import SurrenderMatchService
from matches.services.room import CreateRoomService


User = get_user_model()


class IntegrityFixtureMixin:
    def setUp(self):
        cache.clear()
        self.started_at = timezone.now().replace(microsecond=0)
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.opponent = User.objects.create_user(
            username="opponent", password="Password-938!"
        )
        self.outsider = User.objects.create_user(
            username="outsider", password="Password-938!"
        )
        self.policy = IntegrityPolicy(
            version="v1",
            heartbeat_seconds=10,
            ignore_below_seconds=1,
            strike_seconds=3,
            flag_strikes=2,
            flag_total_seconds=10,
            connection_gap_seconds=30,
        )
        self.match = Match.objects.create(
            room_code="FAIR01",
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=self.started_at,
            duration_seconds=300,
            integrity_monitor_enabled=True,
            integrity_policy_snapshot=self.policy.to_snapshot(),
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
            slot=1,
            is_active=True,
        )
        self.opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
            slot=2,
            is_active=True,
        )
        self.state = MatchIntegrityState.objects.create(
            player=self.host_player,
            last_heartbeat_at=self.started_at,
        )
        MatchIntegrityState.objects.create(
            player=self.opponent_player,
            last_heartbeat_at=self.started_at,
        )
        self.service = MatchIntegrityService()

    def record(self, kind, *, now, event_id=None, **extra):
        event_id = event_id or str(uuid4())
        return self.service.record(
            user=self.host,
            match_id=self.match.pk,
            events=[{"event_id": event_id, "kind": kind, **extra}],
            now=now,
        )


class MatchIntegrityServiceTests(IntegrityFixtureMixin, TestCase):
    def test_absence_thresholds_strikes_and_notice(self):
        self.record("HIDDEN", now=self.started_at)
        result = self.record("VISIBLE", now=self.started_at + timedelta(milliseconds=500))
        self.state.refresh_from_db()
        self.assertEqual(self.state.away_duration_ms, 0)
        self.assertIsNone(result.notice)
        self.assertFalse(MatchIntegrityEvent.objects.exists())

        second_start = self.started_at + timedelta(seconds=10)
        self.record("HIDDEN", now=second_start)
        result = self.record("VISIBLE", now=second_start + timedelta(milliseconds=1500))
        self.state.refresh_from_db()
        self.assertEqual(self.state.away_duration_ms, 1500)
        self.assertEqual(self.state.strike_count, 0)
        self.assertIsNone(result.notice)

        strike_start = self.started_at + timedelta(seconds=20)
        self.record("HIDDEN", now=strike_start)
        result = self.record("VISIBLE", now=strike_start + timedelta(seconds=3))
        self.state.refresh_from_db()
        self.assertEqual(self.state.strike_count, 1)
        self.assertEqual(result.notice.code, "FOCUS_VIOLATION_RECORDED")
        self.assertFalse(self.state.is_flagged)

    def test_second_strike_flags_once(self):
        for offset in (0, 10):
            started_at = self.started_at + timedelta(seconds=offset)
            self.record("HIDDEN", now=started_at)
            self.record("VISIBLE", now=started_at + timedelta(seconds=3))
        self.state.refresh_from_db()
        self.assertEqual(self.state.strike_count, 2)
        self.assertTrue(self.state.is_flagged)
        self.assertEqual(
            self.state.flag_reason, MatchIntegrityState.FlagReason.STRIKES
        )
        self.assertEqual(
            MatchIntegrityEvent.objects.filter(
                kind=MatchIntegrityEvent.Kind.FLAGGED
            ).count(),
            1,
        )

    def test_short_audit_intervals_flag_at_ten_total_seconds(self):
        for index in range(5):
            started_at = self.started_at + timedelta(seconds=index * 5)
            self.record("HIDDEN", now=started_at)
            self.record("VISIBLE", now=started_at + timedelta(seconds=2))
        self.state.refresh_from_db()
        self.assertEqual(self.state.strike_count, 0)
        self.assertEqual(self.state.away_duration_ms, 10_000)
        self.assertTrue(self.state.is_flagged)
        self.assertEqual(
            self.state.flag_reason, MatchIntegrityState.FlagReason.AWAY_TIME
        )

    def test_hidden_then_page_leave_is_one_page_absence(self):
        self.record("HIDDEN", now=self.started_at)
        self.record("PAGE_LEAVE", now=self.started_at + timedelta(seconds=1))
        self.record("PAGE_RETURN", now=self.started_at + timedelta(seconds=4))
        events = MatchIntegrityEvent.objects.exclude(
            kind=MatchIntegrityEvent.Kind.FLAGGED
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().kind, MatchIntegrityEvent.Kind.PAGE_AWAY)
        self.assertEqual(events.get().duration_ms, 4000)

    def test_connection_gap_boundary_flags_without_strike(self):
        self.record("HEARTBEAT", now=self.started_at + timedelta(seconds=29))
        self.assertFalse(
            MatchIntegrityEvent.objects.filter(
                kind=MatchIntegrityEvent.Kind.CONNECTION_GAP
            ).exists()
        )
        self.state.last_heartbeat_at = self.started_at
        self.state.save(update_fields=["last_heartbeat_at"])

        result = self.record(
            "HEARTBEAT", now=self.started_at + timedelta(seconds=30)
        )
        self.state.refresh_from_db()
        self.assertTrue(self.state.is_flagged)
        self.assertEqual(self.state.strike_count, 0)
        self.assertEqual(
            self.state.flag_reason,
            MatchIntegrityState.FlagReason.CONNECTION_GAP,
        )
        self.assertEqual(result.notice.code, "CONNECTION_GAP_RECORDED")

    def test_page_return_after_connection_gap_is_flagged(self):
        result = self.record(
            "PAGE_RETURN", now=self.started_at + timedelta(seconds=30)
        )

        self.state.refresh_from_db()
        self.assertTrue(self.state.is_flagged)
        self.assertEqual(
            self.state.flag_reason,
            MatchIntegrityState.FlagReason.CONNECTION_GAP,
        )
        self.assertEqual(result.notice.code, "CONNECTION_GAP_RECORDED")

    def test_paste_is_audit_only_and_replay_is_idempotent(self):
        event_id = str(uuid4())
        first = self.record(
            "PASTE",
            now=self.started_at,
            event_id=event_id,
            character_count=125,
        )
        second = self.record(
            "PASTE",
            now=self.started_at + timedelta(seconds=1),
            event_id=event_id,
            character_count=125,
        )
        self.state.refresh_from_db()
        self.assertEqual(first.accepted_event_ids, second.accepted_event_ids)
        self.assertEqual(self.state.paste_count, 1)
        self.assertEqual(self.state.paste_character_count, 125)
        self.assertEqual(self.state.strike_count, 0)
        self.assertFalse(self.state.is_flagged)
        event = MatchIntegrityEvent.objects.get(kind=MatchIntegrityEvent.Kind.PASTE)
        self.assertEqual(event.value, 125)

    def test_finalize_closes_an_open_absence(self):
        self.record("PAGE_LEAVE", now=self.started_at)
        ended_at = self.started_at + timedelta(seconds=4)
        with transaction.atomic():
            finalize_match_integrity(
                match=self.match,
                players=[self.host_player, self.opponent_player],
                now=ended_at,
            )
        self.state.refresh_from_db()
        self.assertIsNone(self.state.active_absence_started_at)
        self.assertEqual(self.state.strike_count, 1)
        self.assertEqual(
            MatchIntegrityEvent.objects.get(
                kind=MatchIntegrityEvent.Kind.PAGE_AWAY
            ).duration_ms,
            4000,
        )

    def test_surrender_closes_an_open_absence(self):
        self.record("PAGE_LEAVE", now=self.started_at)
        ended_at = self.started_at + timedelta(seconds=4)

        SurrenderMatchService().surrender(
            user=self.host,
            match_id=self.match.pk,
            now=ended_at,
        )

        self.state.refresh_from_db()
        self.assertIsNone(self.state.active_absence_started_at)
        self.assertEqual(self.state.strike_count, 1)


class MatchIntegrityEndpointTests(IntegrityFixtureMixin, TestCase):
    def payload(self, *, kind="HEARTBEAT", **extra):
        return {
            "client_session_id": str(uuid4()),
            "events": [
                {"event_id": str(uuid4()), "kind": kind, **extra},
            ],
        }

    def test_requires_auth_membership_post_csrf_and_valid_schema(self):
        url = reverse("integrity-events", args=[self.match.pk])
        self.assertEqual(self.client.post(url, self.payload(), content_type="application/json").status_code, 302)

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(url, self.payload(), content_type="application/json").status_code,
            403,
        )
        self.client.force_login(self.host)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(url, {"events": []}, content_type="application/json").status_code,
            400,
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.host)
        self.assertEqual(
            csrf_client.post(url, self.payload(), content_type="application/json").status_code,
            403,
        )

    def test_response_is_private_and_does_not_expose_flags(self):
        self.client.force_login(self.host)
        response = self.client.post(
            reverse("integrity-events", args=[self.match.pk]),
            self.payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(set(response.json()), {"accepted_event_ids", "notice"})
        self.assertNotContains(response, "is_flagged")
        self.assertNotContains(response, self.opponent.username)

    def test_replayed_event_is_accepted_without_counting_twice(self):
        self.client.force_login(self.host)
        url = reverse("integrity-events", args=[self.match.pk])
        payload = self.payload(kind="PASTE", character_count=42)

        first = self.client.post(url, payload, content_type="application/json")
        second = self.client.post(url, payload, content_type="application/json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.state.refresh_from_db()
        self.assertEqual(self.state.paste_count, 1)
        self.assertEqual(self.state.paste_character_count, 42)

    @override_settings(MATCH_INTEGRITY_RATE_LIMIT=1)
    def test_rate_limits_excess_batches(self):
        self.client.force_login(self.host)
        url = reverse("integrity-events", args=[self.match.pk])

        first = self.client.post(
            url,
            self.payload(),
            content_type="application/json",
        )
        second = self.client.post(
            url,
            self.payload(),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["code"], "RATE_LIMITED")

    @override_settings(MATCH_INTEGRITY_MAX_BATCH_SIZE=1)
    def test_rejects_oversized_batch_and_sensitive_extra_fields(self):
        self.client.force_login(self.host)
        url = reverse("integrity-events", args=[self.match.pk])
        payload = self.payload()
        payload["events"].append(
            {"event_id": str(uuid4()), "kind": "HEARTBEAT"}
        )
        self.assertEqual(
            self.client.post(url, payload, content_type="application/json").status_code,
            400,
        )
        payload = self.payload(kind="PASTE", character_count=10)
        payload["events"][0]["clipboard"] = "secret source"
        self.assertEqual(
            self.client.post(url, payload, content_type="application/json").status_code,
            400,
        )


class IntegrityAdminTests(IntegrityFixtureMixin, TestCase):
    def test_audit_models_are_read_only_and_match_filter_is_allowed(self):
        for model in (MatchIntegrityState, MatchIntegrityEvent):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(None))
            self.assertFalse(model_admin.has_change_permission(None))
            self.assertFalse(model_admin.has_delete_permission(None))
        self.host.is_staff = True
        self.host.is_superuser = True
        self.host.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.host)

        response = self.client.get(
            reverse("admin:matches_matchintegritystate_changelist"),
            {"player__match__id__exact": self.match.pk},
        )

        self.assertEqual(response.status_code, 200)


class IntegrityRoomSnapshotTests(TestCase):
    @override_settings(MATCH_INTEGRITY_ENABLED=True)
    def test_new_room_snapshots_current_policy(self):
        user = User.objects.create_user(username="host", password="Password-938!")
        match = CreateRoomService(code_generator=lambda: "POLICY").create(user=user)
        self.assertTrue(match.integrity_monitor_enabled)
        self.assertEqual(
            match.integrity_policy_snapshot,
            current_integrity_policy().to_snapshot(),
        )

    @override_settings(MATCH_INTEGRITY_ENABLED=False)
    def test_disabled_monitor_stores_no_policy(self):
        user = User.objects.create_user(username="host", password="Password-938!")
        match = CreateRoomService(code_generator=lambda: "NOFAIR").create(user=user)
        self.assertFalse(match.integrity_monitor_enabled)
        self.assertEqual(match.integrity_policy_snapshot, {})

    @override_settings(
        MATCH_INTEGRITY_ENABLED=True,
        MATCH_INTEGRITY_FLAG_STRIKES=4,
    )
    def test_policy_snapshot_does_not_follow_later_settings_changes(self):
        user = User.objects.create_user(username="host", password="Password-938!")
        match = CreateRoomService(code_generator=lambda: "FROZEN").create(user=user)

        with override_settings(MATCH_INTEGRITY_FLAG_STRIKES=9):
            self.assertEqual(match.integrity_policy_snapshot["flag_strikes"], 4)


class IntegrityMigrationTests(TransactionTestCase):
    def test_existing_matches_are_not_monitored_or_backfilled(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        old_target = [("matches", "0024_seed_shield")]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        user = old_apps.get_model("auth", "User").objects.create(
            username="legacy-integrity-host"
        )
        legacy_match = old_apps.get_model("matches", "Match").objects.create(
            room_code="OLDMON",
            host_id=user.pk,
            status="PLAYING",
            started_at=timezone.now(),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        apps = executor.loader.project_state(leaves).apps
        migrated = apps.get_model("matches", "Match").objects.get(
            pk=legacy_match.pk
        )

        self.assertFalse(migrated.integrity_monitor_enabled)
        self.assertEqual(migrated.integrity_policy_snapshot, {})
        self.assertEqual(
            apps.get_model("matches", "MatchIntegrityState").objects.count(),
            0,
        )
