from datetime import timedelta

from django.conf import settings
from django.db import models


class Match(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        PLAYING = "PLAYING", "Playing"
        FINISHED = "FINISHED", "Finished"
        CANCELLED = "CANCELLED", "Cancelled"

    room_code = models.CharField(max_length=6, unique=True)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hosted_matches",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=900)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="won_matches",
        null=True,
        blank=True,
    )
    is_draw = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_seconds__gt=0),
                name="match_duration_gt_0",
            ),
            models.CheckConstraint(
                condition=~(
                    models.Q(winner__isnull=False) & models.Q(is_draw=True)
                ),
                name="match_winner_or_draw_not_both",
            ),
        ]

    @property
    def ends_at(self):
        if self.started_at is None:
            return None
        return self.started_at + timedelta(seconds=self.duration_seconds)

    def __str__(self):
        return f"Match {self.room_code}"


class MatchPlayer(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_players",
    )
    score = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_host = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["match", "user"],
                name="matchplayer_match_user_unique",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.match.room_code}"


class MatchProblem(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="match_problems",
    )
    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.PROTECT,
        related_name="match_problems",
    )
    order = models.PositiveIntegerField()
    points = models.PositiveIntegerField()
    title_snapshot = models.CharField(max_length=200)
    statement_snapshot = models.TextField()
    starter_code_snapshot = models.TextField(blank=True)
    difficulty_snapshot = models.CharField(max_length=20)
    first_solver = models.ForeignKey(
        MatchPlayer,
        on_delete=models.SET_NULL,
        related_name="first_solved_problems",
        null=True,
        blank=True,
    )
    first_solved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "problem"],
                name="matchproblem_match_problem_unique",
            ),
            models.UniqueConstraint(
                fields=["match", "order"],
                name="matchproblem_match_order_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(points__gte=1),
                name="matchproblem_points_gte_1",
            ),
        ]
        indexes = [
            models.Index(
                fields=["match", "first_solver"],
                name="matchproblem_solver_idx",
            ),
        ]

    def __str__(self):
        return f"{self.match.room_code} - #{self.order}: {self.title_snapshot}"


class Submission(models.Model):
    class Language(models.TextChoices):
        PYTHON = "PYTHON", "Python"

    class Verdict(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        WRONG_ANSWER = "WRONG_ANSWER", "Wrong answer"
        COMPILATION_ERROR = "COMPILATION_ERROR", "Compilation error"
        RUNTIME_ERROR = "RUNTIME_ERROR", "Runtime error"
        TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED", "Time limit exceeded"
        INTERNAL_ERROR = "INTERNAL_ERROR", "Internal error"

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    player = models.ForeignKey(
        MatchPlayer,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    match_problem = models.ForeignKey(
        MatchProblem,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    source_code = models.TextField()
    language = models.CharField(
        max_length=20,
        choices=Language.choices,
        default=Language.PYTHON,
    )
    verdict = models.CharField(
        max_length=25,
        choices=Verdict.choices,
        default=Verdict.PENDING,
        db_index=True,
    )
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    judge_token = models.CharField(max_length=100, blank=True)
    runtime_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_kb = models.PositiveIntegerField(null=True, blank=True)
    judge_message = models.TextField(blank=True)
    is_score_processed = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=["match", "player"], name="submission_match_player_idx"),
            models.Index(
                fields=["match_problem", "received_at"],
                name="submission_problem_rcvd_idx",
            ),
        ]

    def __str__(self):
        return f"Submission #{self.pk} ({self.verdict})"


class PlayerProblemProgress(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="problem_progress",
    )
    player = models.ForeignKey(
        MatchPlayer,
        on_delete=models.CASCADE,
        related_name="problem_progress",
    )
    match_problem = models.ForeignKey(
        MatchProblem,
        on_delete=models.CASCADE,
        related_name="player_progress",
    )
    is_solved = models.BooleanField(default=False, db_index=True)
    solved_at = models.DateTimeField(null=True, blank=True)
    base_points_awarded = models.PositiveIntegerField(default=0)
    first_solve_bonus_awarded = models.PositiveIntegerField(default=0)
    accepted_submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        related_name="accepted_progress",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "match_problem"],
                name="progress_player_matchproblem_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(first_solve_bonus_awarded__in=[0, 1]),
                name="progress_first_bonus_0_or_1",
            ),
        ]
        indexes = [
            models.Index(
                fields=["match", "player", "is_solved"],
                name="progress_match_player_sol_idx",
            ),
        ]

    def __str__(self):
        return f"{self.player} - {self.match_problem}"
