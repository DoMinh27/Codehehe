from datetime import timedelta

from django.conf import settings
from django.db import models

from .rules import CURRENT_RULESET_VERSION, default_v3_rules_snapshot


class Skill(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    energy_cost = models.PositiveSmallIntegerField()
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Match(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        PLAYING = "PLAYING", "Playing"
        FINISHED = "FINISHED", "Finished"
        CANCELLED = "CANCELLED", "Cancelled"

    class FinishReason(models.TextChoices):
        TIMEOUT = "TIMEOUT", "Hết giờ"
        ALL_SOLVED = "ALL_SOLVED", "Cả hai đã giải hết bài"
        SURRENDER = "SURRENDER", "Đầu hàng"

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
    duration_seconds = models.PositiveIntegerField(default=300)
    ruleset_version = models.CharField(
        max_length=20,
        default=CURRENT_RULESET_VERSION,
    )
    rules_snapshot = models.JSONField(default=default_v3_rules_snapshot)
    ai_review_enabled = models.BooleanField(default=False)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="won_matches",
        null=True,
        blank=True,
    )
    is_draw = models.BooleanField(default=False)
    finish_reason = models.CharField(
        max_length=20,
        choices=FinishReason.choices,
        null=True,
        blank=True,
    )
    surrendered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="surrendered_matches",
        null=True,
        blank=True,
    )
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
            models.CheckConstraint(
                condition=(
                    ~models.Q(finish_reason="SURRENDER")
                    | models.Q(surrendered_by__isnull=False)
                ),
                name="match_surrender_has_player",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(surrendered_by__isnull=True)
                    | models.Q(finish_reason="SURRENDER")
                ),
                name="match_surrender_player_reason",
            ),
        ]

    @property
    def ends_at(self):
        if self.started_at is None:
            return None
        return self.started_at + timedelta(seconds=self.duration_seconds)

    def __str__(self):
        return f"Match {self.room_code}"


class MatchSkill(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="match_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="match_snapshots",
    )
    code_snapshot = models.CharField(max_length=40)
    name_snapshot = models.CharField(max_length=100)
    description_snapshot = models.TextField()
    energy_cost_snapshot = models.PositiveSmallIntegerField()
    duration_seconds_snapshot = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "skill"],
                name="matchskill_match_skill_unique",
            ),
            models.UniqueConstraint(
                fields=["match", "code_snapshot"],
                name="matchskill_match_code_unique",
            ),
        ]

    def __str__(self):
        return f"{self.match.room_code} - {self.name_snapshot}"


class MatchPlayer(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="match_players",
    )
    score = models.PositiveIntegerField(default=0)
    energy = models.PositiveSmallIntegerField(default=0)
    time_penalty_seconds = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_host = models.BooleanField(default=False)
    slot = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["match", "user"],
                name="matchplayer_match_user_unique",
            ),
            models.UniqueConstraint(
                fields=["match", "slot"],
                condition=models.Q(slot__isnull=False),
                name="matchplayer_match_slot_unique",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="matchplayer_one_active_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(slot__in=[1, 2]) | models.Q(slot__isnull=True),
                name="matchplayer_slot_1_or_2",
            ),
            models.CheckConstraint(
                condition=models.Q(energy__gte=0, energy__lte=3),
                name="matchplayer_energy_0_to_3",
            ),
        ]

    @property
    def personal_ends_at(self):
        if self.match.started_at is None or self.match.ends_at is None:
            return None
        penalized_end = self.match.ends_at - timedelta(
            seconds=self.time_penalty_seconds
        )
        return max(self.match.started_at, penalized_end)

    def __str__(self):
        return f"{self.user.username} in {self.match.room_code}"


class MatchPlayerSkill(models.Model):
    player = models.ForeignKey(
        MatchPlayer,
        on_delete=models.CASCADE,
        related_name="skill_inventory",
    )
    match_skill = models.ForeignKey(
        MatchSkill,
        on_delete=models.CASCADE,
        related_name="player_inventory",
    )
    quantity = models.PositiveIntegerField(default=0)
    used_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match_skill_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "match_skill"],
                name="player_matchskill_unique",
            ),
        ]

    def __str__(self):
        return f"{self.player} - {self.match_skill.code_snapshot}"


class SkillUse(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="skill_uses",
    )
    source_player = models.ForeignKey(
        MatchPlayer,
        on_delete=models.CASCADE,
        related_name="skill_uses",
    )
    target_player = models.ForeignKey(
        MatchPlayer,
        on_delete=models.CASCADE,
        related_name="skill_hits",
    )
    match_skill = models.ForeignKey(
        MatchSkill,
        on_delete=models.PROTECT,
        related_name="uses",
    )
    energy_spent = models.PositiveSmallIntegerField()
    idempotency_key = models.CharField(max_length=64)
    used_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-used_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_player", "idempotency_key"],
                name="skilluse_player_idem_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["match", "used_at"],
                name="skilluse_match_used_idx",
            ),
        ]

    def __str__(self):
        return f"{self.source_player} used {self.match_skill.code_snapshot}"


class SkillEffect(models.Model):
    skill_use = models.OneToOneField(
        SkillUse,
        on_delete=models.CASCADE,
        related_name="effect",
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["expires_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("started_at")),
                name="skilleffect_expires_after_start",
            ),
        ]

    def __str__(self):
        # Django creates the ``<relation>_id`` attribute dynamically.
        return f"Effect for skill use #{self.skill_use_id}"  # pyright: ignore[reportAttributeAccessIssue]


class TypingChallenge(models.Model):
    effect = models.OneToOneField(
        SkillEffect,
        on_delete=models.CASCADE,
        related_name="typing_challenge",
    )
    prompt = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["expires_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("started_at")),
                name="typingchallenge_expires_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(completed_at__isnull=True)
                    | (
                        models.Q(completed_at__gte=models.F("started_at"))
                        & models.Q(completed_at__lte=models.F("expires_at"))
                    )
                ),
                name="typingchallenge_completion_in_window",
            ),
        ]

    def __str__(self):
        return f"Typing challenge #{self.pk}"


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
    reference_solution_snapshot = models.TextField(blank=True)
    difficulty_snapshot = models.CharField(max_length=20)
    sample_tests_snapshot = models.JSONField(default=list)
    hidden_tests_snapshot = models.JSONField(default=list)
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
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "match_problem", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="submission_player_problem_idem_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["match", "player"], name="submission_match_player_idx"),
            models.Index(
                fields=["match_problem", "received_at"],
                name="submission_problem_rcvd_idx",
            ),
            models.Index(
                fields=["player", "match_problem", "-received_at", "-id"],
                name="sub_player_prob_time_idx",
            ),
        ]

    def __str__(self):
        return f"Submission #{self.pk} ({self.verdict})"


class SubmissionAIReview(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="ai_reviews",
    )
    progress = models.OneToOneField(
        "PlayerProblemProgress",
        on_delete=models.SET_NULL,
        related_name="ai_review",
        null=True,
        blank=True,
    )
    prompt_version = models.CharField(max_length=40)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    provider = models.CharField(max_length=40, default="groq")
    model = models.CharField(max_length=100)
    result = models.JSONField(default=dict, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    manual_retry_count = models.PositiveSmallIntegerField(default=0)
    failure_retryable = models.BooleanField(default=False)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    reasoning_tokens = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="ai_review_due_idx",
            ),
        ]

    def __str__(self):
        return f"AI review #{self.pk} ({self.status})"


class AIReviewProviderThrottle(models.Model):
    provider = models.CharField(max_length=40, unique=True)
    next_allowed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI throttle for {self.provider}"


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
    reward_processed = models.BooleanField(default=False)
    energy_awarded = models.PositiveSmallIntegerField(default=0)
    skill_awarded = models.ForeignKey(
        MatchSkill,
        on_delete=models.SET_NULL,
        related_name="awarded_progress",
        null=True,
        blank=True,
    )
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
            models.CheckConstraint(
                condition=models.Q(energy_awarded__in=[0, 1]),
                name="progress_energy_award_0_or_1",
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
