"""Match start and finish lifecycle services."""

from dataclasses import dataclass, field
from random import SystemRandom
from typing import Callable

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from matches.models import (
    Match,
    MatchEvent,
    MatchIntegrityState,
    MatchPlayer,
    MatchProblem,
    MatchSkill,
    PlayerProblemProgress,
    Skill,
    Submission,
)
from matches.rules import rules_for_match
from matches.skills.definitions import SKILL_REGISTRY
from problems.models import Problem

from .db import retry_transient_db_lock
from .events import record_event, record_match_finished
from .integrity import finalize_match_integrity
from .scoring import ScoringService


class MatchLifecycleError(Exception):
    """Base class for expected match lifecycle failures."""


class MatchNotFoundError(MatchLifecycleError):
    """Raised when a requested match does not exist."""


class MatchPermissionError(MatchLifecycleError):
    """Raised when a non-host attempts a host-only action."""


class MatchStateError(MatchLifecycleError):
    """Raised when the match is not in the required state."""


class MatchPlayerCountError(MatchLifecycleError):
    """Raised when the match does not have exactly two players."""


class InsufficientProblemsError(MatchLifecycleError):
    """Raised when the problem bank cannot supply the V1 set."""


class InsufficientSkillsError(MatchLifecycleError):
    """Raised when the V2 Skill catalog is incomplete."""


class MatchNotReadyToFinishError(MatchLifecycleError):
    """Raised when neither finish condition has been reached."""


class MatchHasPendingSubmissionsError(MatchLifecycleError):
    """Raised while an on-time submission is still being judged."""


@dataclass
class StartMatchService:
    """Create a frozen four-problem battle and start its server timer."""

    problem_selector: Callable[[list[Problem], int], list[Problem]] = field(
        default_factory=lambda: SystemRandom().sample
    )

    def start(self, *, user, match_id: int) -> Match:
        return retry_transient_db_lock(
            lambda: self._start_once(user=user, match_id=match_id)
        )

    def _start_once(self, *, user, match_id: int) -> Match:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise MatchNotFoundError("Không tìm thấy trận đấu.") from error

            if match.host_id != user.id:
                raise MatchPermissionError("Chỉ host được bắt đầu trận.")
            if match.status != Match.Status.WAITING or match.started_at is not None:
                raise MatchStateError("Trận đấu không còn ở trạng thái chờ.")
            rules = rules_for_match(match)

            players = list(
                MatchPlayer.objects.select_for_update()
                .filter(match=match)
                .order_by("joined_at", "id")
            )
            if len(players) != 2:
                raise MatchPlayerCountError("Phòng cần đúng hai người để bắt đầu.")

            active_skills = {
                skill.code: skill
                for skill in Skill.objects.filter(
                    is_active=True,
                    code__in=rules.required_skill_codes,
                )
            }
            if set(active_skills) != set(rules.required_skill_codes):
                raise InsufficientSkillsError("Cấu hình Skill Battle chưa đầy đủ.")

            eligible_problems = (
                Problem.objects.annotate(
                    hidden_test_count=Count(
                        "test_cases",
                        filter=Q(test_cases__is_sample=False),
                    )
                )
                .filter(
                    is_active=True,
                    hidden_test_count__gt=0,
                )
                .exclude(reference_solution="")
            )
            selected_problems = []
            for difficulty, required_count in rules.problem_counts.items():
                if required_count == 0:
                    continue
                candidates = list(
                    eligible_problems.filter(
                        difficulty=difficulty,
                    ).order_by("order", "id")
                )
                if len(candidates) < required_count:
                    raise InsufficientProblemsError(
                        "Ngân hàng bài tập không đủ cho ruleset của trận."
                    )
                selected_problems.extend(
                    self.problem_selector(candidates, required_count)
                )

            match_problems = []
            for order, problem in enumerate(
                selected_problems,
                start=1,
            ):
                sample_tests = []
                hidden_tests = []
                for test_case in problem.test_cases.order_by("order", "id"):
                    snapshot = {
                        "input_data": test_case.input_data,
                        "expected_output": test_case.expected_output,
                    }
                    if test_case.is_sample:
                        sample_tests.append(snapshot)
                    else:
                        hidden_tests.append(snapshot)
                match_problems.append(
                    MatchProblem(
                        match=match,
                        problem=problem,
                        order=order,
                        points=problem.points,
                        title_snapshot=problem.title,
                        statement_snapshot=problem.statement,
                        starter_code_snapshot=problem.starter_code,
                        reference_solution_snapshot=problem.reference_solution,
                        difficulty_snapshot=problem.difficulty,
                        sample_tests_snapshot=sample_tests,
                        hidden_tests_snapshot=hidden_tests,
                    )
                )
            MatchProblem.objects.bulk_create(match_problems)
            MatchSkill.objects.bulk_create(
                [
                    MatchSkill(
                        match=match,
                        skill=active_skills[code],
                        code_snapshot=active_skills[code].code,
                        name_snapshot=active_skills[code].name,
                        description_snapshot=active_skills[code].description,
                        energy_cost_snapshot=active_skills[code].energy_cost,
                        duration_seconds_snapshot=(
                            active_skills[code].duration_seconds
                        ),
                        policy_snapshot=(SKILL_REGISTRY[code].to_policy_snapshot()),
                    )
                    for code in rules.required_skill_codes
                ]
            )
            PlayerProblemProgress.objects.bulk_create(
                [
                    PlayerProblemProgress(
                        match=match,
                        player=player,
                        match_problem=match_problem,
                    )
                    for player in players
                    for match_problem in match_problems
                ]
            )

            match.status = Match.Status.PLAYING
            match.started_at = timezone.now()
            match.timeline_version = 1
            match.save(
                update_fields=["status", "started_at", "timeline_version", "updated_at"]
            )
            record_event(
                match=match,
                kind=MatchEvent.Kind.MATCH_STARTED,
                event_key="started",
                payload={"duration_seconds": match.duration_seconds},
                now=match.started_at,
            )
            if match.integrity_monitor_enabled:
                MatchIntegrityState.objects.bulk_create(
                    [
                        MatchIntegrityState(
                            player=player,
                            last_heartbeat_at=match.started_at,
                        )
                        for player in players
                    ]
                )
            return match


@dataclass
class FinishMatchService:
    """Idempotently finalize an eligible match and persist its result."""

    scoring_service: ScoringService = field(default_factory=ScoringService)

    def finalize(self, *, match_id: int, now=None) -> Match:
        return retry_transient_db_lock(
            lambda: self._finalize_once(match_id=match_id, now=now)
        )

    def _finalize_once(self, *, match_id: int, now=None) -> Match:
        evaluation_time = now or timezone.now()
        unprocessed_ids = list(
            Submission.objects.filter(
                match_id=match_id,
                is_score_processed=False,
            )
            .exclude(verdict=Submission.Verdict.PENDING)
            .values_list("id", flat=True)
        )
        for submission_id in unprocessed_ids:
            self.scoring_service.process_submission(submission_id)

        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise MatchNotFoundError("Không tìm thấy trận đấu.") from error

            if match.status == Match.Status.FINISHED:
                MatchPlayer.objects.filter(match=match).update(is_active=False)
                return match
            if match.status != Match.Status.PLAYING or match.ends_at is None:
                raise MatchStateError("Trận đấu không ở trạng thái đang chơi.")

            players = list(
                MatchPlayer.objects.select_for_update()
                .filter(match=match)
                .order_by("id")
            )
            if len(players) != 2:
                raise MatchPlayerCountError("Trận đấu cần đúng hai người để kết thúc.")
            problem_count = MatchProblem.objects.filter(match=match).count()
            solved_counts = {
                row["player_id"]: row["count"]
                for row in PlayerProblemProgress.objects.filter(
                    match=match,
                    is_solved=True,
                )
                .values("player_id")
                .annotate(count=Count("id"))
            }
            both_solved_all = problem_count > 0 and all(
                solved_counts.get(player.id, 0) == problem_count for player in players
            )
            player_deadlines = {
                player.id: player.personal_ends_at for player in players
            }
            all_players_terminal = problem_count > 0 and all(
                solved_counts.get(player.id, 0) == problem_count
                or (
                    player_deadlines[player.id] is not None
                    and evaluation_time >= player_deadlines[player.id]
                )
                for player in players
            )
            if not all_players_terminal:
                raise MatchNotReadyToFinishError("Trận đấu chưa đủ điều kiện kết thúc.")

            if Submission.objects.filter(
                match=match,
                verdict=Submission.Verdict.PENDING,
            ).exists():
                raise MatchHasPendingSubmissionsError(
                    "Đang chờ submission hợp lệ hoàn tất."
                )

            if Submission.objects.filter(
                match=match,
                is_score_processed=False,
            ).exists():
                raise MatchHasPendingSubmissionsError(
                    "Đang hoàn tất tính điểm submission."
                )

            highest_score = max(player.score for player in players)
            leaders = [player for player in players if player.score == highest_score]
            match.status = Match.Status.FINISHED
            unfinished_player_deadlines = [
                player_deadlines[player.id]
                for player in players
                if solved_counts.get(player.id, 0) != problem_count
            ]
            match.ended_at = (
                max(unfinished_player_deadlines)
                if unfinished_player_deadlines
                else evaluation_time
            )
            match.finish_reason = (
                Match.FinishReason.ALL_SOLVED
                if both_solved_all
                else Match.FinishReason.TIMEOUT
            )
            match.surrendered_by = None
            if len(leaders) == 1:
                match.winner_id = leaders[0].user_id
                match.is_draw = False
            else:
                match.winner = None
                match.is_draw = True
            match.save(
                update_fields=[
                    "status",
                    "ended_at",
                    "finish_reason",
                    "surrendered_by",
                    "winner",
                    "is_draw",
                    "updated_at",
                ]
            )
            finalize_match_integrity(
                match=match,
                players=players,
                now=match.ended_at,
            )
            MatchPlayer.objects.filter(match=match).update(is_active=False)
            record_match_finished(match=match, players=players)
            return match

    def try_finalize(self, *, match_id: int, now=None) -> Match | None:
        try:
            return self.finalize(match_id=match_id, now=now)
        except (
            MatchHasPendingSubmissionsError,
            MatchNotReadyToFinishError,
            MatchPlayerCountError,
            MatchStateError,
        ):
            return None


@dataclass
class SurrenderMatchService:
    """Immediately finish a playing match in favor of the opponent."""

    def surrender(self, *, user, match_id: int, now=None) -> Match:
        return retry_transient_db_lock(
            lambda: self._surrender_once(user=user, match_id=match_id, now=now)
        )

    def _surrender_once(self, *, user, match_id: int, now=None) -> Match:
        with transaction.atomic():
            try:
                match = Match.objects.select_for_update().get(pk=match_id)
            except Match.DoesNotExist as error:
                raise MatchNotFoundError("Không tìm thấy trận đấu.") from error

            players = list(
                MatchPlayer.objects.select_for_update()
                .filter(match=match)
                .order_by("id")
            )
            current_player = next(
                (player for player in players if player.user_id == user.id),
                None,
            )
            if current_player is None:
                raise MatchPermissionError("Bạn không thuộc trận đấu này.")
            if (
                match.status == Match.Status.FINISHED
                and match.finish_reason == Match.FinishReason.SURRENDER
                and match.surrendered_by_id == user.id
            ):
                MatchPlayer.objects.filter(match=match).update(is_active=False)
                return match
            if match.status != Match.Status.PLAYING:
                raise MatchStateError("Trận đấu không ở trạng thái đang chơi.")
            if len(players) != 2:
                raise MatchPlayerCountError("Trận đấu cần đúng hai người để đầu hàng.")

            opponent = next(
                player for player in players if player.pk != current_player.pk
            )
            match.status = Match.Status.FINISHED
            match.ended_at = now or timezone.now()
            match.finish_reason = Match.FinishReason.SURRENDER
            match.surrendered_by_id = user.id
            match.winner_id = opponent.user_id
            match.is_draw = False
            match.save(
                update_fields=[
                    "status",
                    "ended_at",
                    "finish_reason",
                    "surrendered_by",
                    "winner",
                    "is_draw",
                    "updated_at",
                ]
            )
            finalize_match_integrity(
                match=match,
                players=players,
                now=match.ended_at,
            )
            MatchPlayer.objects.filter(match=match).update(is_active=False)
            record_event(
                match=match,
                kind=MatchEvent.Kind.PLAYER_SURRENDERED,
                event_key="surrendered",
                actor=current_player,
                target=opponent,
                now=match.ended_at,
            )
            record_match_finished(match=match, players=players, now=match.ended_at)
            return match
