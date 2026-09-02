import json
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import (
    MatchPlayerSkill,
    MatchSkill,
    Skill,
    SkillEffect,
    Submission,
    TypingChallenge,
)
from matches.services.run import CodeRunConflictError, CodeRunService
from matches.services.scoring import ScoringService
from matches.services.submission import (
    SubmissionConflictError,
    SubmissionService,
)
from matches.skills.definitions import (
    MIRROR_CODE,
    SKILL_REGISTRY,
    TYPING_CHALLENGE,
)
from matches.skills.rewards import RewardService
from matches.skills.service import SkillService, SkillUseConflictError
from matches.skills.typing import (
    InvalidTypingChallengeError,
    TypingChallengeConflictError,
    TypingChallengeService,
    has_active_typing_challenge,
)
from matches.test_v2 import V2FixtureMixin
from problems.services.judge import FakeCodeRunner, FakeJudgeService


PROMPT = "practice makes progress"


class TypingFixtureMixin(V2FixtureMixin):
    def create_typing_fixture(self, *, room_code):
        self.create_v2_fixture(room_code=room_code)
        skill, _ = Skill.objects.update_or_create(
            code=TYPING_CHALLENGE,
            defaults={
                "name": "Typing Challenge",
                "description": "Type the prompt to unlock actions.",
                "energy_cost": 1,
                "duration_seconds": 20,
                "is_active": True,
            },
        )
        self.match_skills[TYPING_CHALLENGE] = MatchSkill.objects.create(
            match=self.match,
            skill=skill,
            code_snapshot=TYPING_CHALLENGE,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            energy_cost_snapshot=1,
            duration_seconds_snapshot=20,
            policy_snapshot=(SKILL_REGISTRY[TYPING_CHALLENGE].to_policy_snapshot()),
        )

    def activate_typing(self, *, now=None, quantity=1):
        inventory = self.grant(
            self.host_player,
            TYPING_CHALLENGE,
            quantity=quantity,
        )
        result = SkillService(prompt_selector=lambda prompts: PROMPT).use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=TYPING_CHALLENGE,
            target_player_id=self.opponent_player.pk,
            idempotency_key=f"typing-{self.match.room_code}",
            now=now,
        )
        challenge = TypingChallenge.objects.get(effect__skill_use=result.skill_use)
        return result, challenge, inventory


class TypingSkillServiceTests(TypingFixtureMixin, TestCase):
    def setUp(self):
        self.create_typing_fixture(room_code="TYPE01")

    def test_use_creates_atomic_nonstacking_challenge_and_coexists(self):
        now = timezone.now()
        result, challenge, inventory = self.activate_typing(
            now=now,
            quantity=2,
        )

        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertTrue(result.created)
        self.assertEqual(challenge.prompt, PROMPT)
        self.assertEqual(challenge.started_at, now)
        self.assertEqual(challenge.expires_at, now + timedelta(seconds=20))
        self.assertEqual((self.host_player.energy, inventory.quantity), (2, 1))

        with self.assertRaises(SkillUseConflictError):
            SkillService(prompt_selector=lambda prompts: PROMPT).use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=TYPING_CHALLENGE,
                target_player_id=self.opponent_player.pk,
                idempotency_key="typing-second",
                now=now,
            )
        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, inventory.quantity), (2, 1))

        mirror_inventory = self.grant(self.host_player, MIRROR_CODE)
        SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="mirror-with-typing",
            now=now,
        )
        mirror_inventory.refresh_from_db()
        self.assertEqual(mirror_inventory.quantity, 0)
        self.assertEqual(
            SkillEffect.objects.filter(
                skill_use__target_player=self.opponent_player,
                expires_at__gt=now,
            ).count(),
            2,
        )

    def test_target_that_already_finished_is_rejected_without_spending(self):
        self.opponent_progress.is_solved = True
        self.opponent_progress.solved_at = timezone.now()
        self.opponent_progress.save(update_fields=["is_solved", "solved_at"])
        inventory = self.grant(self.host_player, TYPING_CHALLENGE)

        with self.assertRaises(SkillUseConflictError):
            SkillService(prompt_selector=lambda prompts: PROMPT).use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=TYPING_CHALLENGE,
                target_player_id=self.opponent_player.pk,
                idempotency_key="finished-target",
            )

        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, inventory.quantity), (3, 1))

    def test_active_challenge_locks_run_submit_and_skill(self):
        self.activate_typing()

        runner = FakeCodeRunner()
        with self.assertRaises(CodeRunConflictError):
            CodeRunService(runner).run(
                user=self.opponent,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
                input_data="",
            )
        self.assertEqual(runner.calls, [])

        judge = FakeJudgeService()
        with self.assertRaises(SubmissionConflictError):
            SubmissionService(judge).submit(
                user=self.opponent,
                match_id=self.match.pk,
                match_problem_id=self.match_problem.pk,
                source_code="print(1)",
            )
        self.assertEqual(judge.calls, [])
        self.assertFalse(
            Submission.objects.filter(player=self.opponent_player).exists()
        )

        self.grant(self.opponent_player, MIRROR_CODE)
        with self.assertRaises(SkillUseConflictError):
            SkillService().use(
                user=self.opponent,
                match_id=self.match.pk,
                skill_code=MIRROR_CODE,
                target_player_id=self.host_player.pk,
                idempotency_key="locked-skill",
            )

    def test_completion_is_exact_idempotent_and_expiry_unlocks(self):
        now = timezone.now()
        _, challenge, _ = self.activate_typing(now=now)
        service = TypingChallengeService()

        with self.assertRaises(InvalidTypingChallengeError):
            service.complete(
                user=self.opponent,
                match_id=self.match.pk,
                challenge_id=challenge.pk,
                typed_text="Practice makes progress",
                now=now + timedelta(seconds=1),
            )
        self.assertTrue(
            has_active_typing_challenge(
                player_id=self.opponent_player.pk,
                now=now + timedelta(seconds=1),
            )
        )

        completed = service.complete(
            user=self.opponent,
            match_id=self.match.pk,
            challenge_id=challenge.pk,
            typed_text=PROMPT,
            now=now + timedelta(seconds=2),
        )
        replay = service.complete(
            user=self.opponent,
            match_id=self.match.pk,
            challenge_id=challenge.pk,
            typed_text=PROMPT,
            now=now + timedelta(seconds=3),
        )
        challenge.refresh_from_db()
        self.assertTrue(completed.completed_now)
        self.assertFalse(replay.completed_now)
        self.assertIsNotNone(challenge.completed_at)
        self.assertFalse(
            has_active_typing_challenge(
                player_id=self.opponent_player.pk,
                now=now + timedelta(seconds=3),
            )
        )

        self.host_player.energy = 3
        self.host_player.save(update_fields=["energy"])
        MatchPlayerSkill.objects.filter(
            player=self.host_player,
            match_skill=self.match_skills[TYPING_CHALLENGE],
        ).update(quantity=1)
        second = SkillService(prompt_selector=lambda prompts: PROMPT).use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=TYPING_CHALLENGE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="typing-expiry",
            now=now,
        )
        expired = TypingChallenge.objects.get(effect__skill_use=second.skill_use)
        with self.assertRaises(TypingChallengeConflictError):
            service.complete(
                user=self.opponent,
                match_id=self.match.pk,
                challenge_id=expired.pk,
                typed_text=PROMPT,
                now=now + timedelta(seconds=20),
            )
        self.assertFalse(
            has_active_typing_challenge(
                player_id=self.opponent_player.pk,
                now=now + timedelta(seconds=20),
            )
        )

    def test_submission_received_before_challenge_still_scores(self):
        pending = Submission.objects.create(
            match=self.match,
            player=self.opponent_player,
            match_problem=self.match_problem,
            source_code="print(1)",
        )
        self.activate_typing()
        Submission.objects.filter(pk=pending.pk).update(
            verdict=Submission.Verdict.ACCEPTED,
            completed_at=timezone.now(),
        )

        ScoringService(
            reward_service=RewardService(
                selector=lambda skills: self.match_skills[TYPING_CHALLENGE]
            )
        ).process_submission(pending.pk)

        self.opponent_player.refresh_from_db()
        pending.refresh_from_db()
        self.assertTrue(pending.is_score_processed)
        self.assertEqual(self.opponent_player.score, 2)


class TypingChallengeViewTests(TypingFixtureMixin, TestCase):
    def setUp(self):
        self.create_typing_fixture(room_code="TYPEV1")
        _, self.challenge, _ = self.activate_typing()
        self.url = reverse(
            "typing-challenge-complete",
            args=[self.match.pk, self.challenge.pk],
        )

    def test_state_and_html_expose_prompt_only_to_target(self):
        self.client.force_login(self.opponent)
        state = self.client.get(reverse("match-state", args=[self.match.pk]))
        payload = state.json()
        self.assertTrue(payload["my_action_locked"])
        self.assertEqual(payload["typing_challenge"]["prompt"], PROMPT)

        battle = self.client.get(reverse("battle", args=[self.match.pk]))
        self.assertContains(battle, 'id="typing-challenge"')
        self.assertContains(battle, '"typingCompleteUrlTemplate"')

        self.client.force_login(self.host)
        source_state = self.client.get(reverse("match-state", args=[self.match.pk]))
        self.assertFalse(source_state.json()["my_action_locked"])
        self.assertIsNone(source_state.json()["typing_challenge"])
        self.assertNotIn(PROMPT, source_state.content.decode())

    def test_complete_endpoint_auth_csrf_exact_match_and_replay(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.opponent)
        self.assertEqual(
            csrf_client.post(
                self.url,
                data=json.dumps({"typed_text": PROMPT}),
                content_type="application/json",
            ).status_code,
            403,
        )

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(
                self.url,
                data=json.dumps({"typed_text": PROMPT}),
                content_type="application/json",
            ).status_code,
            403,
        )

        self.client.force_login(self.opponent)
        wrong = self.client.post(
            self.url,
            data=json.dumps({"typed_text": f"{PROMPT} "}),
            content_type="application/json",
        )
        self.assertEqual(wrong.status_code, 400)

        completed = self.client.post(
            self.url,
            data=json.dumps({"typed_text": PROMPT}),
            content_type="application/json",
        )
        replay = self.client.post(
            self.url,
            data=json.dumps({"typed_text": PROMPT}),
            content_type="application/json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.json()["completed_now"])
        self.assertEqual(replay.status_code, 200)
        self.assertFalse(replay.json()["completed_now"])

        state = self.client.get(reverse("match-state", args=[self.match.pk]))
        self.assertFalse(state.json()["my_action_locked"])
        self.assertIsNone(state.json()["typing_challenge"])
