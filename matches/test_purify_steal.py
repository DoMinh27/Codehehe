import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import (
    MatchPlayerSkill,
    MatchSkill,
    Skill,
    SkillEffect,
    TypingChallenge,
)
from matches.services.match_state import MatchStateService
from matches.skills.definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    PURIFY,
    SKILL_REGISTRY,
    STEAL,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
)
from matches.skills.service import (
    SkillService,
    SkillUseConflictError,
    SkillUsePermissionError,
)
from matches.skills.typing import has_active_typing_challenge
from matches.test_v2 import V2FixtureMixin


class PurifyStealFixtureMixin(V2FixtureMixin):
    def create_purify_steal_fixture(self, *, room_code):
        self.create_v2_fixture(room_code=room_code)
        for code, name, cost, duration in (
            (PURIFY, "Thanh tẩy", 1, None),
            (STEAL, "Steal", 2, None),
            (TYPING_CHALLENGE, "Thử thách gõ chữ", 1, 20),
        ):
            skill, _ = Skill.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": f"{name} description",
                    "energy_cost": cost,
                    "duration_seconds": duration,
                    "is_active": True,
                },
            )
            self.match_skills[code] = MatchSkill.objects.create(
                match=self.match,
                skill=skill,
                code_snapshot=code,
                name_snapshot=name,
                description_snapshot=skill.description,
                energy_cost_snapshot=cost,
                duration_seconds_snapshot=duration,
                policy_snapshot=SKILL_REGISTRY[code].to_policy_snapshot(),
            )


class PurifySkillTests(PurifyStealFixtureMixin, TestCase):
    def setUp(self):
        self.create_purify_steal_fixture(room_code="PURIFY")

    def use_against_opponent(self, code, *, now, key):
        self.grant(self.host_player, code, energy=3)
        return SkillService(prompt_selector=lambda prompts: prompts[0]).use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=code,
            target_player_id=self.opponent_player.pk,
            idempotency_key=key,
            now=now,
        )

    def test_purify_cancels_the_newest_active_effect_and_records_outcome(self):
        now = timezone.now()
        mirror = self.use_against_opponent(
            MIRROR_CODE,
            now=now,
            key="mirror",
        )
        blur = self.use_against_opponent(
            BLUR_STATEMENT,
            now=now + timedelta(seconds=1),
            key="blur",
        )
        purify_inventory = self.grant(self.opponent_player, PURIFY, energy=3)

        result = SkillService().use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=PURIFY,
            target_player_id=self.opponent_player.pk,
            idempotency_key="purify",
            now=now + timedelta(seconds=2),
        )

        mirror_effect = SkillEffect.objects.get(skill_use=mirror.skill_use)
        blur_effect = SkillEffect.objects.get(skill_use=blur.skill_use)
        self.assertIsNone(mirror_effect.cancelled_at)
        self.assertEqual(blur_effect.cancelled_at, now + timedelta(seconds=2))
        self.assertEqual(
            result.skill_use.outcome_snapshot,
            {
                "kind": "PURIFIED_EFFECT",
                "effect_id": blur_effect.id,
                "skill_code": BLUR_STATEMENT,
                "skill_name": "Làm mờ đề",
            },
        )
        self.opponent_player.refresh_from_db()
        purify_inventory.refresh_from_db()
        self.assertEqual(
            (self.opponent_player.energy, purify_inventory.quantity), (2, 0)
        )

    def test_purify_can_break_typing_action_lock(self):
        now = timezone.now()
        typing = self.use_against_opponent(
            TYPING_CHALLENGE,
            now=now,
            key="typing",
        )
        challenge = TypingChallenge.objects.get(effect__skill_use=typing.skill_use)
        self.grant(self.opponent_player, PURIFY, energy=3)

        SkillService().use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=PURIFY,
            target_player_id=self.opponent_player.pk,
            idempotency_key="purify-typing",
            now=now + timedelta(seconds=1),
        )

        challenge.effect.refresh_from_db()
        self.assertEqual(challenge.effect.cancelled_at, now + timedelta(seconds=1))
        self.assertFalse(
            has_active_typing_challenge(
                player_id=self.opponent_player.id,
                now=now + timedelta(seconds=1),
            )
        )

    def test_purify_without_an_effect_does_not_spend_resources(self):
        inventory = self.grant(self.opponent_player, PURIFY, energy=3)

        with self.assertRaises(SkillUseConflictError):
            SkillService().use(
                user=self.opponent,
                match_id=self.match.pk,
                skill_code=PURIFY,
                target_player_id=self.opponent_player.pk,
                idempotency_key="no-effect",
            )

        self.opponent_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual((self.opponent_player.energy, inventory.quantity), (3, 1))

    def test_purify_does_not_restore_an_applied_time_penalty(self):
        now = timezone.now()
        self.use_against_opponent(
            TIME_DRAIN_60,
            now=now,
            key="time-drain",
        )
        inventory = self.grant(self.opponent_player, PURIFY, energy=3)

        with self.assertRaises(SkillUseConflictError):
            SkillService().use(
                user=self.opponent,
                match_id=self.match.pk,
                skill_code=PURIFY,
                target_player_id=self.opponent_player.pk,
                idempotency_key="purify-time-drain",
                now=now + timedelta(seconds=1),
            )

        self.opponent_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual(self.opponent_player.time_penalty_seconds, 60)
        self.assertEqual(inventory.quantity, 1)

    def test_purify_requires_the_source_as_target(self):
        self.grant(self.opponent_player, PURIFY, energy=3)

        with self.assertRaises(SkillUsePermissionError):
            SkillService().use(
                user=self.opponent,
                match_id=self.match.pk,
                skill_code=PURIFY,
                target_player_id=self.host_player.pk,
                idempotency_key="wrong-target",
            )


class StealSkillTests(PurifyStealFixtureMixin, TestCase):
    def setUp(self):
        self.create_purify_steal_fixture(room_code="STEAL1")

    def test_steal_transfers_one_inventory_unit_without_changing_used_counts(self):
        source_inventory = self.grant(self.host_player, STEAL, energy=3)
        target_inventory = self.grant(
            self.opponent_player,
            MIRROR_CODE,
            quantity=2,
            energy=3,
        )

        result = SkillService(steal_selector=lambda inventory: target_inventory).use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=STEAL,
            target_player_id=self.opponent_player.pk,
            idempotency_key="steal-mirror",
        )

        source_inventory.refresh_from_db()
        target_inventory.refresh_from_db()
        received = MatchPlayerSkill.objects.get(
            player=self.host_player,
            match_skill=self.match_skills[MIRROR_CODE],
        )
        self.host_player.refresh_from_db()
        self.assertEqual((self.host_player.energy, source_inventory.quantity), (1, 0))
        self.assertEqual(
            (target_inventory.quantity, target_inventory.used_count), (1, 0)
        )
        self.assertEqual((received.quantity, received.used_count), (1, 0))
        self.assertEqual(
            result.skill_use.outcome_snapshot["skill_code"],
            MIRROR_CODE,
        )

    def test_steal_excludes_steal_and_does_not_spend_when_no_target_exists(self):
        source_inventory = self.grant(self.host_player, STEAL, energy=3)
        self.grant(self.opponent_player, STEAL, energy=3)

        with self.assertRaises(SkillUseConflictError):
            SkillService().use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=STEAL,
                target_player_id=self.opponent_player.pk,
                idempotency_key="nothing-to-steal",
            )

        self.host_player.refresh_from_db()
        source_inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, source_inventory.quantity), (3, 1))

    def test_steal_is_idempotent(self):
        source_inventory = self.grant(self.host_player, STEAL, quantity=2, energy=3)
        target_inventory = self.grant(self.opponent_player, BLUR_STATEMENT, energy=3)
        service = SkillService(steal_selector=lambda inventory: target_inventory)

        first = service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=STEAL,
            target_player_id=self.opponent_player.pk,
            idempotency_key="same-steal",
        )
        replay = service.use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=STEAL,
            target_player_id=self.opponent_player.pk,
            idempotency_key="same-steal",
        )

        source_inventory.refresh_from_db()
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.skill_use.pk, replay.skill_use.pk)
        self.assertEqual(source_inventory.quantity, 1)

    def test_steal_can_transfer_purify_but_not_itself(self):
        self.grant(self.host_player, STEAL, energy=3)
        target_inventory = self.grant(self.opponent_player, PURIFY, energy=3)

        SkillService(steal_selector=lambda inventory: target_inventory).use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=STEAL,
            target_player_id=self.opponent_player.pk,
            idempotency_key="steal-purify",
        )

        self.assertEqual(
            MatchPlayerSkill.objects.get(
                player=self.host_player,
                match_skill=self.match_skills[PURIFY],
            ).quantity,
            1,
        )


class PurifyStealStateAndApiTests(PurifyStealFixtureMixin, TestCase):
    def setUp(self):
        self.create_purify_steal_fixture(room_code="STATE1")

    def test_state_exposes_only_safe_skill_availability(self):
        self.grant(self.host_player, PURIFY, energy=3)
        self.grant(self.host_player, STEAL, energy=3)

        payload = MatchStateService().get(user=self.host, match_id=self.match.pk)
        skills = {skill["code"]: skill for skill in payload["my_skills"]}

        self.assertEqual(skills[PURIFY]["target_mode"], "SELF")
        self.assertEqual(skills[PURIFY]["ui_group"], "DEFENSIVE")
        self.assertEqual(skills[STEAL]["ui_group"], "OFFENSIVE")
        self.assertTrue(skills[PURIFY]["can_use_while_action_locked"])
        self.assertEqual(
            skills[PURIFY]["unavailable_reason"],
            "Không có hiệu ứng nào để thanh tẩy.",
        )
        self.assertEqual(
            skills[STEAL]["unavailable_reason"],
            "Đối thủ không còn skill có thể đánh cắp.",
        )
        self.assertNotIn("opponent_skills", payload)

    def test_skill_endpoint_returns_safe_purify_outcome(self):
        now = timezone.now()
        self.grant(self.host_player, MIRROR_CODE, energy=3)
        SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.opponent_player.pk,
            idempotency_key="incoming-effect",
            now=now,
        )
        self.grant(self.opponent_player, PURIFY, energy=3)
        self.client.force_login(self.opponent)

        response = self.client.post(
            reverse("skill-use", args=[self.match.pk, PURIFY]),
            data=json.dumps(
                {
                    "target_player_id": self.opponent_player.pk,
                    "idempotency_key": "purify-api",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["outcome"]["kind"], "PURIFIED_EFFECT")
        self.assertNotIn("source_code", response.content.decode())
