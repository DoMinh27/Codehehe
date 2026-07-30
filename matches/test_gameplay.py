from datetime import timedelta
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from problems.models import Problem
from problems.services.judge import FakeJudgeService

from .models import (
    Match,
    MatchPlayer,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    Skill,
    Submission,
)
from .services.gameplay import (
    FinishMatchService,
    InsufficientProblemsError,
    InsufficientSkillsError,
    MatchHasPendingSubmissionsError,
    MatchNotReadyToFinishError,
    MatchPermissionError,
    MatchPlayerCountError,
    MatchStateError,
    StartMatchService,
)
from .services.match_state import (
    MatchStateNotFoundError,
    MatchStatePermissionError,
    MatchStateService,
)
from .services.scoring import ScoringService

User = get_user_model()


class StartMatchServiceTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.opponent = User.objects.create_user(
            username="opponent",
            password="Password-938!",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="Password-938!",
        )
        self.match = Match.objects.create(room_code="START1", host=self.host)
        MatchPlayer.objects.create(match=self.match, user=self.host, is_host=True)
        MatchPlayer.objects.create(match=self.match, user=self.opponent)
        for index in range(2):
            easy_problem = Problem.objects.create(
                slug=f"easy-{index}",
                title=f"Easy {index}",
                statement=f"Easy statement {index}",
                difficulty=Problem.Difficulty.EASY,
                points=1,
                starter_code=f"# easy {index}",
                reference_solution=f"print({index})",
                order=index + 1,
            )
            easy_problem.test_cases.create(
                input_data=str(index),
                expected_output=str(index),
                is_sample=False,
            )
            medium_problem = Problem.objects.create(
                slug=f"medium-{index}",
                title=f"Medium {index}",
                statement=f"Medium statement {index}",
                difficulty=Problem.Difficulty.MEDIUM,
                points=2,
                starter_code=f"# medium {index}",
                reference_solution=f"print({index})",
                order=index + 1,
            )
            medium_problem.test_cases.create(
                input_data=str(index),
                expected_output=str(index),
                is_sample=False,
            )
            hard_problem = Problem.objects.create(
                slug=f"hard-{index}",
                title=f"Hard {index}",
                statement=f"Hard statement {index}",
                difficulty=Problem.Difficulty.HARD,
                points=3,
                starter_code=f"# hard {index}",
                reference_solution=f"print({index})",
                order=index + 1,
            )
            hard_problem.test_cases.create(
                input_data=str(index),
                expected_output=str(index),
                is_sample=False,
            )

    def test_start_creates_frozen_problems_progress_and_timer(self):
        match = StartMatchService().start(user=self.host, match_id=self.match.pk)

        self.assertEqual(match.status, Match.Status.PLAYING)
        self.assertIsNotNone(match.started_at)
        self.assertEqual(match.match_problems.count(), 4)
        self.assertEqual(match.problem_progress.count(), 8)
        self.assertEqual(match.match_skills.count(), 4)
        self.assertEqual(
            list(match.match_problems.values_list("difficulty_snapshot", flat=True)),
            ["EASY", "EASY", "MEDIUM", "HARD"],
        )

        problem = Problem.objects.get(slug="easy-0")
        frozen_reference = MatchProblem.objects.get(
            match=match,
            problem=problem,
        ).reference_solution_snapshot
        problem.title = "Changed after start"
        problem.reference_solution = "print('changed')"
        problem.save()
        snapshot = MatchProblem.objects.get(match=match, problem=problem)
        self.assertEqual(snapshot.title_snapshot, "Easy 0")
        self.assertEqual(snapshot.reference_solution_snapshot, frozen_reference)

    def test_start_selects_two_problems_from_each_difficulty(self):
        for index in range(2, 5):
            for difficulty in (
                Problem.Difficulty.EASY,
                Problem.Difficulty.MEDIUM,
            ):
                problem = Problem.objects.create(
                    slug=f"{difficulty.lower()}-{index}",
                    title=f"{difficulty.title()} {index}",
                    statement=f"{difficulty.title()} statement {index}",
                    difficulty=difficulty,
                    points=1,
                    reference_solution=f"print({index})",
                    order=index + 1,
                )
                problem.test_cases.create(
                    input_data=str(index),
                    expected_output=str(index),
                    is_sample=False,
                )

        service = StartMatchService(
            problem_selector=lambda candidates, count: candidates[-count:]
        )
        match = service.start(user=self.host, match_id=self.match.pk)

        self.assertEqual(
            list(match.match_problems.values_list("problem__slug", flat=True)),
            ["easy-3", "easy-4", "medium-4", "hard-1"],
        )
        self.assertEqual(
            match.match_problems.values("problem_id").distinct().count(),
            4,
        )

    def test_start_uses_problem_distribution_from_match_rules_snapshot(self):
        snapshot = deepcopy(self.match.rules_snapshot)
        snapshot["problem_counts"] = {
            "EASY": 1,
            "MEDIUM": 2,
            "HARD": 1,
        }
        self.match.rules_snapshot = snapshot
        self.match.save(update_fields=["rules_snapshot"])

        match = StartMatchService().start(
            user=self.host,
            match_id=self.match.pk,
        )

        self.assertEqual(
            list(
                match.match_problems.values_list(
                    "difficulty_snapshot",
                    flat=True,
                )
            ),
            ["EASY", "MEDIUM", "MEDIUM", "HARD"],
        )

    def test_only_host_can_start(self):
        with self.assertRaises(MatchPermissionError):
            StartMatchService().start(
                user=self.opponent,
                match_id=self.match.pk,
            )

    def test_start_requires_exactly_two_players(self):
        MatchPlayer.objects.filter(match=self.match, user=self.opponent).delete()
        with self.assertRaises(MatchPlayerCountError):
            StartMatchService().start(user=self.host, match_id=self.match.pk)

    def test_start_is_not_repeatable(self):
        StartMatchService().start(user=self.host, match_id=self.match.pk)
        with self.assertRaises(MatchStateError):
            StartMatchService().start(user=self.host, match_id=self.match.pk)

        self.assertEqual(MatchProblem.objects.filter(match=self.match).count(), 4)
        self.assertEqual(PlayerProblemProgress.objects.filter(match=self.match).count(), 8)

    def test_insufficient_problem_set_rolls_back(self):
        Problem.objects.filter(difficulty=Problem.Difficulty.MEDIUM).delete()

        with self.assertRaises(InsufficientProblemsError):
            StartMatchService().start(user=self.host, match_id=self.match.pk)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.WAITING)
        self.assertIsNone(self.match.started_at)
        self.assertFalse(MatchProblem.objects.filter(match=self.match).exists())

    def test_missing_hard_problem_rolls_back(self):
        Problem.objects.filter(difficulty=Problem.Difficulty.HARD).delete()

        with self.assertRaises(InsufficientProblemsError):
            StartMatchService().start(user=self.host, match_id=self.match.pk)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.WAITING)
        self.assertIsNone(self.match.started_at)
        self.assertFalse(MatchProblem.objects.filter(match=self.match).exists())

    def test_incomplete_skill_catalog_rolls_back(self):
        Skill.objects.filter(code="MIRROR_CODE").update(is_active=False)

        with self.assertRaises(InsufficientSkillsError):
            StartMatchService().start(user=self.host, match_id=self.match.pk)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.WAITING)
        self.assertIsNone(self.match.started_at)
        self.assertFalse(MatchProblem.objects.filter(match=self.match).exists())
        self.assertFalse(MatchSkill.objects.filter(match=self.match).exists())


class StartMatchViewTests(TestCase):
    def setUp(self):
        StartMatchServiceTests.setUp(self)

    def test_host_start_redirects_to_battle(self):
        self.client.force_login(self.host)

        response = self.client.post(reverse("match-start", args=[self.match.pk]))

        self.assertRedirects(response, reverse("battle", args=[self.match.pk]))

    def test_outsider_cannot_view_battle(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("battle", args=[self.match.pk]))

        self.assertEqual(response.status_code, 403)


class BattleViewTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.opponent = User.objects.create_user(
            username="opponent",
            password="Password-938!",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="Password-938!",
        )
        self.match = Match.objects.create(
            room_code="BATTLE",
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        MatchPlayer.objects.create(match=self.match, user=self.host, is_host=True)
        MatchPlayer.objects.create(match=self.match, user=self.opponent)
        for index, difficulty in enumerate(
            [
                Problem.Difficulty.EASY,
                Problem.Difficulty.EASY,
                Problem.Difficulty.MEDIUM,
                Problem.Difficulty.MEDIUM,
            ],
            start=1,
        ):
            problem = Problem.objects.create(
                slug=f"battle-{index}",
                title=f"Original {index}",
                statement=f"Original statement {index}",
                difficulty=difficulty,
                points=1 if difficulty == Problem.Difficulty.EASY else 2,
                starter_code=f"# starter {index}",
                order=index,
            )
            problem.test_cases.create(
                input_data=f"sample-input-{index}",
                expected_output=f"sample-output-{index}",
                is_sample=True,
            )
            problem.test_cases.create(
                input_data=f"secret-input-{index}",
                expected_output=f"secret-output-{index}",
                is_sample=False,
            )
            MatchProblem.objects.create(
                match=self.match,
                problem=problem,
                order=index,
                points=problem.points,
                title_snapshot=f"Frozen {index}",
                statement_snapshot=f"Frozen statement {index}",
                starter_code_snapshot=problem.starter_code,
                difficulty_snapshot=problem.difficulty,
                sample_tests_snapshot=[
                    {
                        "input_data": f"sample-input-{index}",
                        "expected_output": f"sample-output-{index}",
                    }
                ],
                hidden_tests_snapshot=[
                    {
                        "input_data": f"secret-input-{index}",
                        "expected_output": f"secret-output-{index}",
                    }
                ],
            )

    def test_battle_uses_snapshots_samples_and_submission_routes(self):
        self.client.force_login(self.host)

        response = self.client.get(reverse("battle", args=[self.match.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/battle.html")
        self.assertContains(response, "Frozen 1")
        self.assertNotContains(response, "Original statement 1")
        self.assertContains(response, "sample-input-1")
        self.assertNotContains(response, "secret-input-1")
        self.assertNotContains(response, "secret-output-1")
        for match_problem in self.match.match_problems.all():
            self.assertContains(
                response,
                reverse("submission-create", args=[self.match.pk, match_problem.pk]),
            )

    def test_outsider_cannot_view_battle(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("battle", args=[self.match.pk])).status_code,
            403,
        )

    def test_refresh_does_not_change_server_timer(self):
        self.client.force_login(self.host)
        started_at = self.match.started_at

        self.client.get(reverse("battle", args=[self.match.pk]))
        self.client.get(reverse("battle", args=[self.match.pk]))

        self.match.refresh_from_db()
        self.assertEqual(self.match.started_at, started_at)


class ScoringServiceTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host", password="Password-938!")
        self.opponent = User.objects.create_user(
            username="opponent",
            password="Password-938!",
        )
        self.match = Match.objects.create(
            room_code="SCORE1",
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        self.opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
        )
        self.problem = Problem.objects.create(
            slug="scoring",
            title="Scoring",
            statement="Score this.",
            difficulty=Problem.Difficulty.MEDIUM,
            points=2,
        )
        self.match_problem = MatchProblem.objects.create(
            match=self.match,
            problem=self.problem,
            order=1,
            points=2,
            title_snapshot=self.problem.title,
            statement_snapshot=self.problem.statement,
            difficulty_snapshot=self.problem.difficulty,
            hidden_tests_snapshot=[
                {"input_data": "hidden", "expected_output": "output"}
            ],
        )
        for player in (self.host_player, self.opponent_player):
            PlayerProblemProgress.objects.create(
                match=self.match,
                player=player,
                match_problem=self.match_problem,
            )
        self.scoring = ScoringService()

    def submission(self, player, verdict):
        return Submission.objects.create(
            match=self.match,
            player=player,
            match_problem=self.match_problem,
            source_code="print(1)",
            verdict=verdict,
            completed_at=(
                None if verdict == Submission.Verdict.PENDING else timezone.now()
            ),
        )

    def test_first_accepted_awards_base_and_bonus_once(self):
        accepted = self.submission(
            self.host_player,
            Submission.Verdict.ACCEPTED,
        )

        self.scoring.process_submission(accepted.pk)
        self.scoring.process_submission(accepted.pk)

        self.host_player.refresh_from_db()
        progress = PlayerProblemProgress.objects.get(player=self.host_player)
        self.match_problem.refresh_from_db()
        self.assertEqual(self.host_player.score, 3)
        self.assertEqual(progress.base_points_awarded, 2)
        self.assertEqual(progress.first_solve_bonus_awarded, 1)
        self.assertEqual(self.match_problem.first_solver, self.host_player)

    def test_duplicate_accepted_does_not_add_score(self):
        first = self.submission(self.host_player, Submission.Verdict.ACCEPTED)
        self.scoring.process_submission(first.pk)
        duplicate = self.submission(self.host_player, Submission.Verdict.ACCEPTED)

        self.scoring.process_submission(duplicate.pk)

        self.host_player.refresh_from_db()
        self.assertEqual(self.host_player.score, 3)

    def test_first_solve_bonus_uses_match_rules_snapshot(self):
        snapshot = deepcopy(self.match.rules_snapshot)
        snapshot["scoring"]["first_solve_bonus"] = 0
        self.match.rules_snapshot = snapshot
        self.match.save(update_fields=["rules_snapshot"])
        accepted = self.submission(
            self.host_player,
            Submission.Verdict.ACCEPTED,
        )

        self.scoring.process_submission(accepted.pk)

        self.host_player.refresh_from_db()
        progress = PlayerProblemProgress.objects.get(player=self.host_player)
        self.match_problem.refresh_from_db()
        self.assertEqual(self.host_player.score, 2)
        self.assertEqual(progress.first_solve_bonus_awarded, 0)
        self.assertEqual(self.match_problem.first_solver, self.host_player)

    def test_wrong_answer_does_not_add_score(self):
        wrong = self.submission(
            self.host_player,
            Submission.Verdict.WRONG_ANSWER,
        )
        self.scoring.process_submission(wrong.pk)

        self.host_player.refresh_from_db()
        wrong.refresh_from_db()
        self.assertEqual(self.host_player.score, 0)
        self.assertTrue(wrong.is_score_processed)

    def test_earlier_pending_defers_and_then_wins_first_solve(self):
        earlier = self.submission(self.host_player, Submission.Verdict.PENDING)
        later = self.submission(
            self.opponent_player,
            Submission.Verdict.ACCEPTED,
        )

        self.scoring.process_submission(later.pk)
        self.opponent_player.refresh_from_db()
        self.match_problem.refresh_from_db()
        self.assertEqual(self.opponent_player.score, 2)
        self.assertIsNone(self.match_problem.first_solver)

        Submission.objects.filter(pk=earlier.pk).update(
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )
        self.scoring.process_submission(earlier.pk)

        self.host_player.refresh_from_db()
        self.opponent_player.refresh_from_db()
        self.match_problem.refresh_from_db()
        self.assertEqual(self.host_player.score, 3)
        self.assertEqual(self.opponent_player.score, 2)
        self.assertEqual(self.match_problem.first_solver, self.host_player)

    def test_later_accepted_wins_after_earlier_pending_is_wrong(self):
        earlier = self.submission(self.host_player, Submission.Verdict.PENDING)
        later = self.submission(
            self.opponent_player,
            Submission.Verdict.ACCEPTED,
        )
        self.scoring.process_submission(later.pk)

        Submission.objects.filter(pk=earlier.pk).update(
            verdict=Submission.Verdict.WRONG_ANSWER,
            completed_at=timezone.now(),
        )
        self.scoring.process_submission(earlier.pk)

        self.opponent_player.refresh_from_db()
        self.match_problem.refresh_from_db()
        self.assertEqual(self.opponent_player.score, 3)
        self.assertEqual(self.match_problem.first_solver, self.opponent_player)

    @patch("matches.views.submissions.Judge0Service.from_environment")
    def test_submission_endpoint_runs_scoring(self, judge_factory):
        judge_factory.return_value = FakeJudgeService()
        self.problem.test_cases.create(
            input_data="1",
            expected_output="1",
            is_sample=False,
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "submission-create",
                args=[self.match.pk, self.match_problem.pk],
            ),
            data='{"source_code": "print(input())"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.host_player.refresh_from_db()
        self.assertEqual(self.host_player.score, 3)


class LifecycleFixtureMixin:
    def create_lifecycle_fixture(self, *, room_code="FINISH"):
        self.host = User.objects.create_user(
            username=f"host-{room_code}",
            password="Password-938!",
        )
        self.opponent = User.objects.create_user(
            username=f"opponent-{room_code}",
            password="Password-938!",
        )
        self.outsider = User.objects.create_user(
            username=f"outsider-{room_code}",
            password="Password-938!",
        )
        self.match = Match.objects.create(
            room_code=room_code,
            host=self.host,
            status=Match.Status.PLAYING,
            started_at=timezone.now(),
        )
        self.host_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.host,
            is_host=True,
        )
        self.opponent_player = MatchPlayer.objects.create(
            match=self.match,
            user=self.opponent,
        )
        self.match_problems = []
        for index in range(1, 5):
            problem = Problem.objects.create(
                slug=f"{room_code.lower()}-{index}",
                title=f"Problem {index}",
                statement=f"Statement {index}",
                difficulty=(
                    Problem.Difficulty.EASY
                    if index <= 2
                    else Problem.Difficulty.MEDIUM
                ),
                points=1 if index <= 2 else 2,
                order=index,
            )
            problem.test_cases.create(
                input_data=f"sample-{index}",
                expected_output=f"sample-output-{index}",
                is_sample=True,
            )
            problem.test_cases.create(
                input_data=f"hidden-{index}",
                expected_output=f"hidden-output-{index}",
                is_sample=False,
            )
            match_problem = MatchProblem.objects.create(
                match=self.match,
                problem=problem,
                order=index,
                points=problem.points,
                title_snapshot=problem.title,
                statement_snapshot=problem.statement,
                starter_code_snapshot="# Python",
                difficulty_snapshot=problem.difficulty,
                sample_tests_snapshot=[
                    {
                        "input_data": f"sample-{index}",
                        "expected_output": f"sample-output-{index}",
                    }
                ],
                hidden_tests_snapshot=[
                    {
                        "input_data": f"hidden-{index}",
                        "expected_output": f"hidden-output-{index}",
                    }
                ],
            )
            self.match_problems.append(match_problem)
            for player in (self.host_player, self.opponent_player):
                PlayerProblemProgress.objects.create(
                    match=self.match,
                    player=player,
                    match_problem=match_problem,
                )

    def expire_match(self):
        Match.objects.filter(pk=self.match.pk).update(
            started_at=timezone.now()
            - timedelta(seconds=self.match.duration_seconds + 1)
        )
        self.match.refresh_from_db()

    def solve_all(self):
        PlayerProblemProgress.objects.filter(match=self.match).update(
            is_solved=True,
            solved_at=timezone.now(),
        )


class FinishMatchServiceTests(LifecycleFixtureMixin, TestCase):
    def setUp(self):
        self.create_lifecycle_fixture()
        self.service = FinishMatchService()

    def test_rejects_match_before_finish_condition(self):
        with self.assertRaises(MatchNotReadyToFinishError):
            self.service.finalize(match_id=self.match.pk)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.PLAYING)

    def test_waits_for_on_time_pending_submission_after_deadline(self):
        self.expire_match()
        pending = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problems[0],
            source_code="print(1)",
        )
        Submission.objects.filter(pk=pending.pk).update(
            received_at=self.match.ends_at - timedelta(seconds=1)
        )

        with self.assertRaises(MatchHasPendingSubmissionsError):
            self.service.finalize(match_id=self.match.pk)

        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.PLAYING)

    def test_timeout_selects_winner_and_is_idempotent(self):
        self.expire_match()
        self.host_player.score = 4
        self.host_player.save(update_fields=["score"])
        self.opponent_player.score = 2
        self.opponent_player.save(update_fields=["score"])

        finished = self.service.finalize(match_id=self.match.pk)
        ended_at = finished.ended_at
        finished_again = self.service.finalize(match_id=self.match.pk)

        self.assertEqual(finished_again.status, Match.Status.FINISHED)
        self.assertEqual(finished_again.winner, self.host)
        self.assertFalse(finished_again.is_draw)
        self.assertEqual(
            finished_again.finish_reason,
            Match.FinishReason.TIMEOUT,
        )
        self.assertEqual(finished_again.ended_at, ended_at)

    def test_equal_scores_finish_as_draw(self):
        self.expire_match()

        finished = self.service.finalize(match_id=self.match.pk)

        self.assertTrue(finished.is_draw)
        self.assertIsNone(finished.winner)

    def test_both_players_solving_all_problems_finishes_early(self):
        self.solve_all()

        finished = self.service.finalize(match_id=self.match.pk)

        self.assertEqual(finished.status, Match.Status.FINISHED)
        self.assertEqual(
            finished.finish_reason,
            Match.FinishReason.ALL_SOLVED,
        )
        self.assertLess(finished.ended_at, self.match.ends_at)

    def test_unprocessed_terminal_submission_is_scored_before_finish(self):
        self.expire_match()
        accepted = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problems[0],
            source_code="print(1)",
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )

        finished = self.service.finalize(match_id=self.match.pk)

        accepted.refresh_from_db()
        self.host_player.refresh_from_db()
        self.assertTrue(accepted.is_score_processed)
        self.assertEqual(self.host_player.score, 2)
        self.assertEqual(finished.winner, self.host)


class MatchLifecycleViewTests(LifecycleFixtureMixin, TestCase):
    def setUp(self):
        self.create_lifecycle_fixture(room_code="STATE1")

    def test_state_is_private_read_only_and_has_constant_query_count(self):
        self.client.force_login(self.host)
        url = reverse("match-state", args=[self.match.pk])
        before = {
            "match": Match.objects.count(),
            "submissions": Submission.objects.count(),
            "progress": PlayerProblemProgress.objects.count(),
        }

        with CaptureQueriesContext(connection) as first_queries:
            response = self.client.get(url)
        with CaptureQueriesContext(connection) as second_queries:
            second_response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(first_queries), len(second_queries))
        self.assertLessEqual(len(first_queries), 8)
        payload = response.json()
        self.assertEqual(payload["status"], Match.Status.PLAYING)
        self.assertEqual(len(payload["first_solvers"]), 4)
        self.assertIn("server_time", payload)
        self.assertIn("remaining_seconds", payload)
        self.assertNotIn("source_code", response.content.decode())
        self.assertNotIn("hidden-1", response.content.decode())
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            before,
            {
                "match": Match.objects.count(),
                "submissions": Submission.objects.count(),
                "progress": PlayerProblemProgress.objects.count(),
            },
        )

    def test_state_rejects_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("match-state", args=[self.match.pk]))
        self.assertEqual(response.status_code, 403)

    def test_state_service_is_deterministic_and_enforces_membership(self):
        now = self.match.started_at + timedelta(seconds=10)

        payload = MatchStateService().get(
            user=self.host,
            match_id=self.match.pk,
            now=now,
        )

        self.assertEqual(payload["server_time"], now.isoformat())
        self.assertEqual(
            payload["remaining_seconds"],
            self.match.duration_seconds - 10,
        )
        with self.assertRaises(MatchStatePermissionError):
            MatchStateService().get(
                user=self.outsider,
                match_id=self.match.pk,
                now=now,
            )
        with self.assertRaises(MatchStateNotFoundError):
            MatchStateService().get(
                user=self.host,
                match_id=999999,
                now=now,
            )

    def test_finalize_endpoint_returns_409_202_then_200(self):
        self.client.force_login(self.host)
        url = reverse("match-finalize", args=[self.match.pk])
        self.assertEqual(self.client.post(url).status_code, 409)

        self.expire_match()
        pending = Submission.objects.create(
            match=self.match,
            player=self.host_player,
            match_problem=self.match_problems[0],
            source_code="print(1)",
        )
        Submission.objects.filter(pk=pending.pk).update(
            received_at=self.match.ends_at - timedelta(seconds=1)
        )
        self.assertEqual(self.client.post(url).status_code, 202)

        Submission.objects.filter(pk=pending.pk).update(
            verdict=Submission.Verdict.WRONG_ANSWER,
            completed_at=timezone.now(),
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Match.Status.FINISHED)

    def test_finalize_requires_member_post_and_csrf(self):
        url = reverse("match-finalize", args=[self.match.pk])
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(url).status_code, 403)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.host)
        csrf_client.get(reverse("battle", args=[self.match.pk]))
        self.assertEqual(csrf_client.post(url).status_code, 403)
        token = csrf_client.cookies["csrftoken"].value
        self.assertEqual(
            csrf_client.post(url, HTTP_X_CSRFTOKEN=token).status_code,
            409,
        )

    def test_result_is_restricted_and_shows_final_summary(self):
        self.expire_match()
        self.host_player.score = 3
        self.host_player.save(update_fields=["score"])
        FinishMatchService().finalize(match_id=self.match.pk)
        url = reverse("match-result", args=[self.match.pk])

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.outsider.is_staff = True
        self.outsider.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.host)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/result.html")
        self.assertContains(response, self.host.username)
        self.assertContains(response, "3 điểm")

    def test_battle_redirects_to_result_after_finish(self):
        self.expire_match()
        FinishMatchService().finalize(match_id=self.match.pk)
        self.client.force_login(self.host)

        response = self.client.get(reverse("battle", args=[self.match.pk]))

        self.assertRedirects(
            response,
            reverse("match-result", args=[self.match.pk]),
        )

    @patch("matches.views.submissions.Judge0Service.from_environment")
    def test_last_accepted_submission_finishes_match_early(self, judge_factory):
        judge_factory.return_value = FakeJudgeService()
        last_problem = self.match_problems[-1]
        for progress in PlayerProblemProgress.objects.filter(match=self.match):
            if (
                progress.player_id == self.host_player.id
                and progress.match_problem_id == last_problem.id
            ):
                continue
            progress.is_solved = True
            progress.solved_at = timezone.now()
            progress.base_points_awarded = progress.match_problem.points
            progress.save(
                update_fields=[
                    "is_solved",
                    "solved_at",
                    "base_points_awarded",
                    "updated_at",
                ]
            )
        self.host_player.score = 4
        self.host_player.save(update_fields=["score"])
        self.opponent_player.score = 6
        self.opponent_player.save(update_fields=["score"])
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "submission-create",
                args=[self.match.pk, last_problem.pk],
            ),
            data='{"source_code": "print(1)"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertEqual(self.match.winner, self.host)
