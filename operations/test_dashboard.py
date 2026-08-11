import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import PlayerActivityDay
from matches.models import (
    Match,
    MatchPlayer,
    MatchProblem,
    Submission,
    SubmissionAIReview,
)
from problems.models import Problem
from problems.services.judge import (
    Judge0ConfigurationError,
    Judge0UnavailableError,
)

from .dashboard import (
    JUDGE_HEALTH_CACHE_KEY,
    _heartbeat_health,
    _judge_health,
    build_dashboard_snapshot,
)
from .models import WorkerHeartbeat


def dashboard_payload():
    health = {
        key: {"status": "ok", "label": "Hoạt động", "detail": "OK"}
        for key in ("web", "database", "judge0", "ai_worker", "match_sweeper")
    }
    return {
        "generated_at": timezone.now().isoformat(),
        "health": health,
        "counters": {
            "waiting_matches": 0,
            "playing_matches": 0,
            "playing_players": 0,
            "pending_submissions": 0,
            "active_ai_reviews": 0,
            "alerts": 0,
        },
        "alerts": [],
        "live_matches": [],
        "submissions": {
            "total": 0,
            "ac_rate": 0.0,
            "pending": 0,
            "stale": 0,
            "average_latency_ms": None,
            "p95_latency_ms": None,
            "verdicts": [],
            "internal_errors": [],
        },
        "ai_reviews": {
            "counts": {status: 0 for status, _ in SubmissionAIReview.Status.choices},
            "oldest_eligible_at": None,
            "success_rate": 0.0,
            "provider": "openrouter",
            "configured_model": "openrouter/free",
            "actual_model": None,
            "tokens": {"input": 0, "output": 0, "reasoning": 0},
            "errors": [],
            "last_completed_at": None,
        },
        "kpis": {
            "new_accounts": 0,
            "active_players": 0,
            "finished_matches": 0,
            "cancelled_matches": 0,
        },
    }


class DashboardPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="root", password="secret"
        )
        self.staff = user_model.objects.create_user(
            username="operator", password="secret", is_staff=True
        )
        self.dashboard_url = reverse("operations:dashboard")
        self.state_url = reverse("operations:dashboard_state")

    def test_anonymous_user_is_redirected_to_admin_login(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_staff_without_dashboard_permission_receives_403(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.state_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_header_link_respects_dashboard_permission(self):
        self.client.force_login(self.staff)
        without_permission = self.client.get(reverse("admin:index"))

        permission = Permission.objects.get(codename="view_operations_dashboard")
        self.staff.user_permissions.add(permission)
        self.staff = get_user_model().objects.get(pk=self.staff.pk)
        self.client.force_login(self.staff)
        with_permission = self.client.get(reverse("admin:index"))

        self.assertNotContains(without_permission, self.dashboard_url)
        self.assertContains(with_permission, self.dashboard_url)

    def test_staff_with_permission_can_read_no_store_state(self):
        permission = Permission.objects.get(codename="view_operations_dashboard")
        self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)

        with patch(
            "operations.views.get_dashboard_snapshot",
            return_value=dashboard_payload(),
        ):
            response = self.client.get(self.state_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_limited_operator_does_not_receive_sensitive_admin_links(self):
        permission = Permission.objects.get(codename="view_operations_dashboard")
        self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)
        payload = dashboard_payload()
        payload["alerts"] = [{"url": "/admin/matches/submission/"}]
        payload["live_matches"] = [
            {"url": "/admin/matches/match/1/change/"}
        ]
        payload["submissions"]["internal_errors"] = [
            {"url": "/admin/matches/submission/2/change/"}
        ]

        with patch(
            "operations.views.get_dashboard_snapshot",
            return_value=payload,
        ):
            response = self.client.get(self.state_url)

        body = response.json()
        self.assertEqual(body["alerts"][0]["url"], "")
        self.assertEqual(body["live_matches"][0]["url"], "")
        self.assertEqual(body["submissions"]["internal_errors"][0]["url"], "")
        self.assertEqual(payload["alerts"][0]["url"], "/admin/matches/submission/")

    def test_superuser_keeps_admin_drilldown_links(self):
        self.client.force_login(self.superuser)
        payload = dashboard_payload()
        payload["alerts"] = [{"url": "/admin/matches/submission/"}]

        with patch(
            "operations.views.get_dashboard_snapshot",
            return_value=payload,
        ):
            response = self.client.get(self.state_url)

        self.assertEqual(
            response.json()["alerts"][0]["url"],
            "/admin/matches/submission/",
        )

    def test_superuser_can_open_dashboard(self):
        self.client.force_login(self.superuser)

        with patch(
            "operations.views.get_dashboard_snapshot",
            return_value=dashboard_payload(),
        ):
            response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "Web App")
        self.assertContains(response, "Phòng đang chờ")
        self.assertContains(response, "Submission và Judge0")

    def test_manual_state_refresh_bypasses_snapshot_cache(self):
        self.client.force_login(self.superuser)

        with patch(
            "operations.views.get_dashboard_snapshot",
            return_value=dashboard_payload(),
        ) as mocked_snapshot:
            response = self.client.get(self.state_url, {"refresh": "1"})

        self.assertEqual(response.status_code, 200)
        mocked_snapshot.assert_called_once_with(force=True)


class DashboardHealthTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("operations.services.health.Judge0Service.from_environment")
    def test_judge_health_is_cached_and_reports_latency(self, from_environment):
        judge = Mock()
        from_environment.return_value = judge

        first = _judge_health()
        second = _judge_health()

        self.assertEqual(first["status"], "ok")
        self.assertIn("latency_ms", first)
        self.assertEqual(first, second)
        judge.healthcheck.assert_called_once_with()

    @patch("operations.services.health.Judge0Service.from_environment")
    def test_judge_configuration_error_is_safe(self, from_environment):
        from_environment.side_effect = Judge0ConfigurationError("secret endpoint")

        result = _judge_health()

        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret endpoint", json.dumps(result))

    @patch("operations.services.health.Judge0Service.from_environment")
    def test_judge_timeout_is_unavailable(self, from_environment):
        judge = Mock()
        judge.healthcheck.side_effect = Judge0UnavailableError("private detail")
        from_environment.return_value = judge

        result = _judge_health()

        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("private detail", json.dumps(result))

    @patch("operations.services.health.Judge0Service.from_environment")
    def test_unexpected_judge_error_is_safe(self, from_environment):
        from_environment.side_effect = ValueError("secret malformed URL")

        result = _judge_health()

        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret malformed URL", json.dumps(result))

    @override_settings(OPERATIONS_JUDGE_SLOW_MS=1000)
    @patch("operations.services.health.time.perf_counter", side_effect=(10.0, 11.2))
    @patch("operations.services.health.Judge0Service.from_environment")
    def test_slow_judge_is_degraded(self, from_environment, _perf_counter):
        from_environment.return_value = Mock()

        result = _judge_health()

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["latency_ms"], 1200)

    @override_settings(AI_REVIEW_ENABLED=False)
    def test_disabled_ai_worker_does_not_require_heartbeat(self):
        result = _heartbeat_health(
            heartbeat=None,
            now=timezone.now(),
            stale_seconds=90,
            disabled=True,
        )

        self.assertEqual(result["status"], "disabled")

    def test_failed_and_stale_heartbeats_have_distinct_states(self):
        now = timezone.now()
        failed = WorkerHeartbeat.objects.create(
            worker=WorkerHeartbeat.Worker.AI_REVIEW,
            status=WorkerHeartbeat.Status.FAILED,
            last_heartbeat_at=now,
            last_failure_at=now,
            error_code="PROVIDER_ERROR",
        )
        stale = WorkerHeartbeat.objects.create(
            worker=WorkerHeartbeat.Worker.MATCH_SWEEPER,
            status=WorkerHeartbeat.Status.OK,
            last_heartbeat_at=now - timedelta(minutes=2),
            last_success_at=now - timedelta(minutes=2),
        )

        failed_state = _heartbeat_health(
            heartbeat=failed, now=now, stale_seconds=90
        )
        stale_state = _heartbeat_health(
            heartbeat=stale, now=now, stale_seconds=60
        )

        self.assertEqual(failed_state["status"], "unavailable")
        self.assertEqual(stale_state["status"], "degraded")

    def test_newer_success_wins_over_legacy_failed_status(self):
        now = timezone.now()
        heartbeat = WorkerHeartbeat.objects.create(
            worker=WorkerHeartbeat.Worker.AI_REVIEW,
            status=WorkerHeartbeat.Status.FAILED,
            last_heartbeat_at=now,
            last_failure_at=now - timedelta(seconds=2),
            last_success_at=now - timedelta(seconds=1),
            error_code="OLD_FAILURE",
        )

        result = _heartbeat_health(
            heartbeat=heartbeat,
            now=now,
            stale_seconds=90,
        )

        self.assertEqual(result["status"], "ok")


@override_settings(
    AI_REVIEW_ENABLED=True,
    AI_REVIEW_PROVIDER="openrouter",
    AI_REVIEW_MODEL="openrouter/free",
    MATCH_PENDING_SUBMISSION_TIMEOUT_SECONDS=120,
    OPERATIONS_WAITING_STALE_SECONDS=1800,
    OPERATIONS_MATCH_GRACE_SECONDS=60,
    OPERATIONS_AI_QUEUE_WARNING_SECONDS=600,
    OPERATIONS_AI_WORKER_STALE_SECONDS=90,
    OPERATIONS_SWEEPER_STALE_SECONDS=60,
    OPERATIONS_AI_FAILURE_WINDOW_SECONDS=900,
    OPERATIONS_AI_FAILURE_WARNING_COUNT=3,
)
class DashboardSnapshotTests(TestCase):
    def setUp(self):
        cache.clear()
        self.now = timezone.now()
        user_model = get_user_model()
        self.host = user_model.objects.create_user(username="host")
        self.guest = user_model.objects.create_user(username="guest")
        self.problem = Problem.objects.create(
            slug="dashboard-problem",
            title="Dashboard problem",
            statement="Public statement",
            difficulty=Problem.Difficulty.EASY,
            points=1,
            reference_solution="REFERENCE_SECRET",
        )

    def create_match(
        self,
        *,
        status,
        started_at=None,
        duration_seconds=300,
        host=None,
    ):
        host = host or self.host
        match = Match.objects.create(
            room_code=f"D{Match.objects.count():05d}",
            host=host,
            status=status,
            started_at=started_at,
            duration_seconds=duration_seconds,
        )
        host_player = MatchPlayer.objects.create(
            match=match,
            user=host,
            slot=1,
            score=1,
            is_host=True,
            is_active=status in {Match.Status.WAITING, Match.Status.PLAYING},
        )
        if status == Match.Status.PLAYING:
            MatchPlayer.objects.create(
                match=match,
                user=self.guest,
                slot=2,
                score=0,
                is_active=True,
            )
        match_problem = MatchProblem.objects.create(
            match=match,
            problem=self.problem,
            order=1,
            points=1,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            reference_solution_snapshot="SNAPSHOT_SECRET",
            difficulty_snapshot=self.problem.difficulty,
            hidden_tests_snapshot=[{"input": "HIDDEN_SECRET", "output": "1"}],
        )
        return match, host_player, match_problem

    @patch("operations.dashboard._judge_health")
    def test_snapshot_reports_live_state_alerts_and_never_serializes_secrets(
        self, judge_health
    ):
        judge_health.return_value = {
            "status": "ok",
            "label": "Hoạt động",
            "detail": "OK",
            "latency_ms": 10,
        }
        WorkerHeartbeat.objects.create(
            worker=WorkerHeartbeat.Worker.AI_REVIEW,
            status=WorkerHeartbeat.Status.OK,
            last_heartbeat_at=self.now,
            last_success_at=self.now,
        )
        WorkerHeartbeat.objects.create(
            worker=WorkerHeartbeat.Worker.MATCH_SWEEPER,
            status=WorkerHeartbeat.Status.OK,
            last_heartbeat_at=self.now,
            last_success_at=self.now,
        )
        playing, player, match_problem = self.create_match(
            status=Match.Status.PLAYING,
            started_at=self.now - timedelta(minutes=10),
            duration_seconds=300,
        )
        waiting_host = get_user_model().objects.create_user(username="waiting-host")
        waiting, _waiting_player, _waiting_problem = self.create_match(
            status=Match.Status.WAITING,
            host=waiting_host,
        )
        Match.objects.filter(pk=waiting.pk).update(
            created_at=self.now - timedelta(hours=1)
        )
        pending = Submission.objects.create(
            match=playing,
            player=player,
            match_problem=match_problem,
            source_code="SOURCE_SECRET",
            verdict=Submission.Verdict.PENDING,
        )
        Submission.objects.filter(pk=pending.pk).update(
            received_at=self.now - timedelta(minutes=5)
        )

        with CaptureQueriesContext(connection) as queries:
            snapshot = build_dashboard_snapshot(now=self.now)
        serialized = json.dumps(snapshot)
        query_sql = " ".join(query["sql"].lower() for query in queries.captured_queries)
        codes = {alert["code"] for alert in snapshot["alerts"]}

        self.assertEqual(snapshot["counters"]["playing_matches"], 1)
        self.assertEqual(snapshot["counters"]["waiting_matches"], 1)
        self.assertEqual(snapshot["counters"]["playing_players"], 2)
        self.assertIn("STALE_SUBMISSIONS", codes)
        self.assertIn("OVERDUE_MATCHES", codes)
        self.assertIn("STALE_WAITING_MATCHES", codes)
        self.assertNotIn("SOURCE_SECRET", serialized)
        self.assertNotIn("REFERENCE_SECRET", serialized)
        self.assertNotIn("SNAPSHOT_SECRET", serialized)
        self.assertNotIn("HIDDEN_SECRET", serialized)
        self.assertNotIn("source_code", query_sql)
        self.assertNotIn("reference_solution_snapshot", query_sql)
        self.assertNotIn("hidden_tests_snapshot", query_sql)

    @patch("operations.dashboard._judge_health")
    def test_submission_ai_and_daily_aggregates_are_calculated(self, judge_health):
        judge_health.return_value = {
            "status": "ok",
            "label": "Hoạt động",
            "detail": "OK",
        }
        WorkerHeartbeat.objects.bulk_create(
            [
                WorkerHeartbeat(
                    worker=WorkerHeartbeat.Worker.AI_REVIEW,
                    status=WorkerHeartbeat.Status.OK,
                    last_heartbeat_at=self.now,
                    last_success_at=self.now,
                ),
                WorkerHeartbeat(
                    worker=WorkerHeartbeat.Worker.MATCH_SWEEPER,
                    status=WorkerHeartbeat.Status.OK,
                    last_heartbeat_at=self.now,
                    last_success_at=self.now,
                ),
            ]
        )
        match, player, match_problem = self.create_match(
            status=Match.Status.FINISHED,
            started_at=self.now - timedelta(minutes=5),
        )
        Match.objects.filter(pk=match.pk).update(ended_at=self.now)
        submissions = []
        for index, verdict in enumerate(
            (
                Submission.Verdict.ACCEPTED,
                Submission.Verdict.WRONG_ANSWER,
                Submission.Verdict.INTERNAL_ERROR,
                Submission.Verdict.COMPILATION_ERROR,
            )
        ):
            submission = Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code=f"code-{index}",
                verdict=verdict,
            )
            received_at = self.now - timedelta(minutes=index + 1)
            Submission.objects.filter(pk=submission.pk).update(
                received_at=received_at,
                completed_at=received_at + timedelta(milliseconds=(index + 1) * 100),
            )
            submission.refresh_from_db()
            submissions.append(submission)

        SubmissionAIReview.objects.create(
            submission=submissions[0],
            prompt_version="v2",
            status=SubmissionAIReview.Status.COMPLETED,
            provider="openrouter",
            model="nvidia/free",
            completed_at=self.now,
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=25,
        )
        SubmissionAIReview.objects.create(
            submission=submissions[1],
            prompt_version="v2",
            status=SubmissionAIReview.Status.FAILED,
            provider="openrouter",
            model="nvidia/free",
            error_code="PROVIDER_ERROR",
        )
        PlayerActivityDay.objects.create(
            user=self.host,
            activity_date=timezone.localdate(self.now),
            first_activity_at=self.now,
        )

        snapshot = build_dashboard_snapshot(now=self.now)

        self.assertEqual(snapshot["submissions"]["total"], 4)
        self.assertEqual(snapshot["submissions"]["ac_rate"], 25.0)
        self.assertEqual(snapshot["submissions"]["average_latency_ms"], 250)
        self.assertEqual(snapshot["submissions"]["p95_latency_ms"], 400)
        self.assertEqual(snapshot["ai_reviews"]["success_rate"], 50.0)
        self.assertEqual(snapshot["ai_reviews"]["actual_model"], "nvidia/free")
        self.assertEqual(snapshot["ai_reviews"]["tokens"]["input"], 100)
        self.assertEqual(snapshot["kpis"]["active_players"], 1)
        self.assertEqual(snapshot["kpis"]["finished_matches"], 1)

    @patch("operations.dashboard._judge_health")
    def test_ai_queue_warning_uses_time_job_became_eligible(self, judge_health):
        judge_health.return_value = {
            "status": "ok",
            "label": "Hoạt động",
            "detail": "OK",
        }
        match, player, match_problem = self.create_match(
            status=Match.Status.FINISHED,
            started_at=self.now - timedelta(hours=3),
        )
        reviews = []
        retry_times = (
            self.now - timedelta(seconds=1),
            self.now - timedelta(minutes=11),
            None,
        )
        for index, retry_at in enumerate(retry_times):
            submission = Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code=f"code-{index}",
                verdict=Submission.Verdict.ACCEPTED,
            )
            review = SubmissionAIReview.objects.create(
                submission=submission,
                prompt_version=f"v{index}",
                status=SubmissionAIReview.Status.PENDING,
                provider="openrouter",
                model="openrouter/free",
                next_attempt_at=retry_at,
            )
            reviews.append(review)
        SubmissionAIReview.objects.filter(pk__in=[review.pk for review in reviews]).update(
            created_at=self.now - timedelta(hours=2)
        )

        snapshot = build_dashboard_snapshot(now=self.now)

        delayed_alert = next(
            alert
            for alert in snapshot["alerts"]
            if alert["code"] == "DELAYED_AI_QUEUE"
        )
        self.assertEqual(delayed_alert["count"], 2)

    @patch("operations.dashboard._judge_health")
    def test_oldest_eligible_ai_job_uses_effective_due_time(self, judge_health):
        judge_health.return_value = {
            "status": "ok",
            "label": "Hoạt động",
            "detail": "OK",
        }
        match, player, match_problem = self.create_match(
            status=Match.Status.FINISHED,
            started_at=self.now - timedelta(hours=3),
        )
        due_times = (
            self.now - timedelta(minutes=1),
            self.now - timedelta(minutes=5),
        )
        review_ids = []
        for index, due_at in enumerate(due_times):
            submission = Submission.objects.create(
                match=match,
                player=player,
                match_problem=match_problem,
                source_code=f"effective-due-{index}",
                verdict=Submission.Verdict.ACCEPTED,
            )
            review = SubmissionAIReview.objects.create(
                submission=submission,
                prompt_version=f"due-v{index}",
                status=SubmissionAIReview.Status.PENDING,
                provider="openrouter",
                model="openrouter/free",
                next_attempt_at=due_at,
            )
            review_ids.append(review.pk)
        SubmissionAIReview.objects.filter(pk__in=review_ids).update(
            created_at=self.now - timedelta(hours=2)
        )

        snapshot = build_dashboard_snapshot(now=self.now)

        self.assertEqual(
            snapshot["ai_reviews"]["oldest_eligible_at"],
            due_times[1].isoformat(),
        )

    @patch("operations.dashboard._judge_health")
    def test_cancelled_match_kpi_uses_cancellation_time(self, judge_health):
        judge_health.return_value = {
            "status": "ok",
            "label": "Hoạt động",
            "detail": "OK",
        }
        recent, _player, _problem = self.create_match(
            status=Match.Status.CANCELLED,
        )
        old_host = get_user_model().objects.create_user(username="old-cancel-host")
        old, _old_player, _old_problem = self.create_match(
            status=Match.Status.CANCELLED,
            host=old_host,
        )
        Match.objects.filter(pk=recent.pk).update(ended_at=self.now)
        Match.objects.filter(pk=old.pk).update(
            ended_at=self.now - timedelta(days=2)
        )

        snapshot = build_dashboard_snapshot(now=self.now)

        self.assertEqual(snapshot["kpis"]["cancelled_matches"], 1)

    def tearDown(self):
        cache.delete(JUDGE_HEALTH_CACHE_KEY)
