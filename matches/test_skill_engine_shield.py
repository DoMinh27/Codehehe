import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import MatchEvent, MatchPlayerSkill, MatchSkill, Skill, SkillEffect
from matches.rules import rules_for_match
from matches.services.events import present_event
from matches.services.match_state import MatchStateService
from matches.skills.definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    OPPONENT,
    PURIFY,
    SELF,
    SHIELD,
    SKILL_REGISTRY,
    STEAL,
    TIME_DRAIN_60,
    TYPING_CHALLENGE,
    policy_for_match_skill,
)
from matches.skills.service import SkillService, SkillUseConflictError
from matches.test_purify_steal import PurifyStealFixtureMixin


class ShieldFixtureMixin(PurifyStealFixtureMixin):
    def create_shield_fixture(self, *, room_code="SHIELD"):
        self.create_purify_steal_fixture(room_code=room_code)
        skill, _ = Skill.objects.update_or_create(
            code=SHIELD,
            defaults={
                "name": "Shield",
                "description": "Chặn skill tấn công hợp lệ tiếp theo.",
                "energy_cost": 1,
                "duration_seconds": 45,
                "is_active": True,
            },
        )
        self.match_skills[SHIELD] = MatchSkill.objects.create(
            match=self.match,
            skill=skill,
            code_snapshot=SHIELD,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            energy_cost_snapshot=skill.energy_cost,
            duration_seconds_snapshot=skill.duration_seconds,
            policy_snapshot=SKILL_REGISTRY[SHIELD].to_policy_snapshot(),
        )

    def activate_shield(self, *, now, quantity=1, key="shield"):
        inventory, _ = MatchPlayerSkill.objects.get_or_create(
            player=self.host_player,
            match_skill=self.match_skills[SHIELD],
            defaults={"quantity": quantity},
        )
        if inventory.quantity < quantity:
            inventory.quantity = quantity
            inventory.save(update_fields=["quantity", "updated_at"])
        self.host_player.energy = 3
        self.host_player.save(update_fields=["energy"])
        result = SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=SHIELD,
            target_player_id=self.host_player.pk,
            idempotency_key=key,
            now=now,
        )
        return result, inventory


class SkillPolicyAndRulesTests(ShieldFixtureMixin, TestCase):
    def setUp(self):
        self.create_shield_fixture(room_code="POLICY")

    def test_v31_snapshot_keeps_six_skills(self):
        snapshot = deepcopy(self.match.rules_snapshot)
        snapshot["required_skill_codes"].remove(SHIELD)
        self.match.ruleset_version = "v3.1"
        self.match.rules_snapshot = snapshot
        self.match.save(update_fields=["ruleset_version", "rules_snapshot"])

        rules = rules_for_match(self.match)

        self.assertEqual(len(rules.required_skill_codes), 6)
        self.assertNotIn(SHIELD, rules.required_skill_codes)

    def test_policy_snapshot_does_not_follow_registry_changes(self):
        match_skill = self.match_skills[SHIELD]
        frozen = match_skill.policy_snapshot
        changed = replace(SKILL_REGISTRY[SHIELD], target_mode=OPPONENT)

        with patch.dict(SKILL_REGISTRY, {SHIELD: changed}):
            policy = policy_for_match_skill(match_skill)

        self.assertEqual(policy.target_mode, SELF)
        self.assertEqual(match_skill.policy_snapshot, frozen)


class ShieldSkillTests(ShieldFixtureMixin, TestCase):
    def setUp(self):
        self.create_shield_fixture(room_code="GUARD1")

    def test_shield_is_a_45_second_self_effect_and_cannot_stack(self):
        now = timezone.now()
        first, inventory = self.activate_shield(
            now=now,
            quantity=2,
            key="shield-first",
        )

        effect = SkillEffect.objects.get(skill_use=first.skill_use)
        self.assertEqual(effect.expires_at, now + timedelta(seconds=45))
        self.assertEqual(first.skill_use.source_player, self.host_player)
        self.assertEqual(first.skill_use.target_player, self.host_player)

        with self.assertRaises(SkillUseConflictError) as raised:
            SkillService().use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=SHIELD,
                target_player_id=self.host_player.pk,
                idempotency_key="shield-second",
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(raised.exception.reason_code, "EFFECT_ALREADY_ACTIVE")
        self.host_player.refresh_from_db()
        inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, inventory.quantity), (2, 1))

    def test_shield_blocks_all_five_offensive_skills_after_validation(self):
        now = timezone.now()
        shield_inventory = MatchPlayerSkill.objects.create(
            player=self.host_player,
            match_skill=self.match_skills[SHIELD],
            quantity=6,
        )
        attacks = (
            MIRROR_CODE,
            BLUR_STATEMENT,
            TIME_DRAIN_60,
            TYPING_CHALLENGE,
            STEAL,
        )
        attack_inventory = {
            code: MatchPlayerSkill.objects.create(
                player=self.opponent_player,
                match_skill=self.match_skills[code],
                quantity=1,
            )
            for code in attacks
        }

        for index, code in enumerate(attacks):
            with self.subTest(code=code):
                moment = now + timedelta(seconds=index * 3)
                self.host_player.energy = 3
                self.host_player.save(update_fields=["energy"])
                shield_result = SkillService().use(
                    user=self.host,
                    match_id=self.match.pk,
                    skill_code=SHIELD,
                    target_player_id=self.host_player.pk,
                    idempotency_key=f"shield-{code}",
                    now=moment,
                )
                self.opponent_player.energy = 3
                self.opponent_player.save(update_fields=["energy"])
                quantity_before_attack = MatchPlayerSkill.objects.get(
                    pk=shield_inventory.pk
                ).quantity
                attack_result = SkillService(
                    steal_selector=lambda rows: next(
                        row for row in rows if row.match_skill.code_snapshot == SHIELD
                    )
                ).use(
                    user=self.opponent,
                    match_id=self.match.pk,
                    skill_code=code,
                    target_player_id=self.host_player.pk,
                    idempotency_key=f"attack-{code}",
                    now=moment + timedelta(seconds=1),
                )

                shield_effect = SkillEffect.objects.get(
                    skill_use=shield_result.skill_use
                )
                shield_effect.refresh_from_db()
                attack_inventory[code].refresh_from_db()
                self.opponent_player.refresh_from_db()
                self.assertEqual(
                    attack_result.skill_use.outcome_snapshot["kind"],
                    "BLOCKED_BY_SHIELD",
                )
                self.assertIsNotNone(shield_effect.consumed_at)
                self.assertEqual(attack_inventory[code].quantity, 0)
                self.assertEqual(attack_inventory[code].used_count, 1)
                self.assertEqual(
                    self.opponent_player.energy,
                    3 - self.match_skills[code].energy_cost_snapshot,
                )
                self.assertFalse(
                    SkillEffect.objects.filter(
                        skill_use=attack_result.skill_use
                    ).exists()
                )
                self.assertEqual(self.host_player.time_penalty_seconds, 0)
                self.assertEqual(
                    MatchPlayerSkill.objects.get(pk=shield_inventory.pk).quantity,
                    quantity_before_attack,
                )

        self.assertEqual(
            SkillEffect.objects.filter(
                skill_use__match_skill=self.match_skills[SHIELD],
                consumed_at__isnull=False,
            ).count(),
            5,
        )

    def test_invalid_steal_does_not_spend_or_consume_shield(self):
        now = timezone.now()
        shield_result, _ = self.activate_shield(now=now)
        steal_inventory = self.grant(self.opponent_player, STEAL, energy=3)

        with self.assertRaises(SkillUseConflictError) as raised:
            SkillService().use(
                user=self.opponent,
                match_id=self.match.pk,
                skill_code=STEAL,
                target_player_id=self.host_player.pk,
                idempotency_key="invalid-steal",
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(raised.exception.reason_code, "NO_STEALABLE_SKILL")
        shield_result.skill_use.effect.refresh_from_db()
        self.opponent_player.refresh_from_db()
        steal_inventory.refresh_from_db()
        self.assertIsNone(shield_result.skill_use.effect.consumed_at)
        self.assertEqual(
            (self.opponent_player.energy, steal_inventory.quantity), (3, 1)
        )

    def test_only_first_valid_attack_consumes_shield_and_replay_is_idempotent(self):
        now = timezone.now()
        shield_result, _ = self.activate_shield(now=now)
        mirror_inventory = self.grant(
            self.opponent_player,
            MIRROR_CODE,
            quantity=2,
            energy=3,
        )
        service = SkillService()

        blocked = service.use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="blocked-mirror",
            now=now + timedelta(seconds=1),
        )
        replay = service.use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="blocked-mirror",
            now=now + timedelta(seconds=1),
        )
        applied = service.use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="applied-mirror",
            now=now + timedelta(seconds=2),
        )

        mirror_inventory.refresh_from_db()
        shield_result.skill_use.effect.refresh_from_db()
        self.assertFalse(replay.created)
        self.assertEqual(replay.skill_use.pk, blocked.skill_use.pk)
        self.assertIsNotNone(shield_result.skill_use.effect.consumed_at)
        self.assertTrue(
            SkillEffect.objects.filter(skill_use=applied.skill_use).exists()
        )
        self.assertEqual(
            (mirror_inventory.quantity, mirror_inventory.used_count), (0, 2)
        )

    def test_expired_shield_does_not_block(self):
        now = timezone.now()
        shield_result, _ = self.activate_shield(now=now)
        self.grant(self.opponent_player, MIRROR_CODE, energy=3)

        result = SkillService().use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="after-expiry",
            now=now + timedelta(seconds=46),
        )

        shield_result.skill_use.effect.refresh_from_db()
        self.assertIsNone(shield_result.skill_use.effect.consumed_at)
        self.assertTrue(SkillEffect.objects.filter(skill_use=result.skill_use).exists())
        self.assertEqual(result.skill_use.outcome_snapshot, {})

    def test_purify_skips_beneficial_shield_and_cancels_harmful_effect(self):
        now = timezone.now()
        self.grant(self.opponent_player, MIRROR_CODE, energy=3)
        mirror = SkillService().use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="harmful",
            now=now,
        )
        shield, _ = self.activate_shield(
            now=now + timedelta(seconds=1),
            key="beneficial",
        )
        purify_inventory = self.grant(self.host_player, PURIFY, energy=2)

        purified = SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=PURIFY,
            target_player_id=self.host_player.pk,
            idempotency_key="purify-harmful",
            now=now + timedelta(seconds=2),
        )

        mirror.skill_use.effect.refresh_from_db()
        shield.skill_use.effect.refresh_from_db()
        purify_inventory.refresh_from_db()
        self.assertEqual(
            purified.skill_use.outcome_snapshot["skill_code"],
            MIRROR_CODE,
        )
        self.assertIsNotNone(mirror.skill_use.effect.cancelled_at)
        self.assertIsNone(shield.skill_use.effect.cancelled_at)
        self.assertEqual(purify_inventory.quantity, 0)

    def test_shield_cannot_be_activated_during_typing_lock(self):
        now = timezone.now()
        self.grant(self.opponent_player, TYPING_CHALLENGE, energy=3)
        SkillService(prompt_selector=lambda prompts: prompts[0]).use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=TYPING_CHALLENGE,
            target_player_id=self.host_player.pk,
            idempotency_key="typing-lock",
            now=now,
        )
        shield_inventory = self.grant(self.host_player, SHIELD, energy=3)

        with self.assertRaises(SkillUseConflictError) as raised:
            SkillService().use(
                user=self.host,
                match_id=self.match.pk,
                skill_code=SHIELD,
                target_player_id=self.host_player.pk,
                idempotency_key="shield-locked",
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(raised.exception.reason_code, "ACTION_LOCKED")
        self.host_player.refresh_from_db()
        shield_inventory.refresh_from_db()
        self.assertEqual((self.host_player.energy, shield_inventory.quantity), (3, 1))

    def test_steal_can_transfer_inactive_shield_inventory(self):
        shield_inventory = self.grant(self.host_player, SHIELD, energy=3)
        self.grant(self.opponent_player, STEAL, energy=3)

        result = SkillService(
            steal_selector=lambda rows: next(
                row for row in rows if row.match_skill.code_snapshot == SHIELD
            )
        ).use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=STEAL,
            target_player_id=self.host_player.pk,
            idempotency_key="steal-shield",
        )

        shield_inventory.refresh_from_db()
        received = MatchPlayerSkill.objects.get(
            player=self.opponent_player,
            match_skill=self.match_skills[SHIELD],
        )
        self.assertEqual(result.skill_use.outcome_snapshot["skill_code"], SHIELD)
        self.assertEqual(shield_inventory.quantity, 0)
        self.assertEqual((received.quantity, received.used_count), (1, 0))


class ShieldStateApiAndTimelineTests(ShieldFixtureMixin, TestCase):
    def setUp(self):
        self.create_shield_fixture(room_code="GUARD2")
        self.match.timeline_version = 1
        self.match.save(update_fields=["timeline_version"])

    def test_state_uses_stable_availability_code_for_active_shield(self):
        now = timezone.now()
        self.activate_shield(now=now, quantity=2)

        payload = MatchStateService().get(
            user=self.host,
            match_id=self.match.pk,
            now=now + timedelta(seconds=1),
        )
        shield = next(
            skill for skill in payload["my_skills"] if skill["code"] == SHIELD
        )

        self.assertEqual(shield["target_mode"], SELF)
        self.assertEqual(shield["ui_group"], "DEFENSIVE")
        self.assertEqual(shield["unavailable_code"], "EFFECT_ALREADY_ACTIVE")
        self.assertEqual(shield["unavailable_reason"], "Hiệu ứng này đang hoạt động.")
        self.assertIn(SHIELD, [effect["code"] for effect in payload["active_effects"]])

    def test_api_and_timeline_report_blocked_outcome_without_sensitive_data(self):
        now = timezone.now()
        self.activate_shield(now=now)
        self.grant(self.opponent_player, MIRROR_CODE, energy=3)
        self.client.force_login(self.opponent)

        response = self.client.post(
            reverse("skill-use", args=[self.match.pk, MIRROR_CODE]),
            data=json.dumps(
                {
                    "target_player_id": self.host_player.pk,
                    "idempotency_key": "blocked-api",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["outcome"]["kind"], "BLOCKED_BY_SHIELD")
        self.assertIsNone(body["effect"])
        self.assertNotIn("inventory", response.content.decode())
        event = self.match.events.get(
            kind=MatchEvent.Kind.SKILL_USED,
            payload__skill_code=MIRROR_CODE,
        )
        self.assertEqual(event.payload["outcome_kind"], "BLOCKED_BY_SHIELD")
        self.assertNotIn("duration_seconds", event.payload)
        self.assertIn(
            "đã bị Shield chặn",
            present_event(event, self.match.started_at)["text"],
        )

        defender_state = MatchStateService().get(
            user=self.host,
            match_id=self.match.pk,
        )
        blocked_use = defender_state["recent_skill_uses"][-1]
        self.assertEqual(blocked_use["outcome_kind"], "BLOCKED_BY_SHIELD")
        self.assertNotIn("opponent_skills", defender_state)


class ShieldMigrationTests(TransactionTestCase):
    def test_upgrade_freezes_old_policies_without_adding_shield_to_old_match(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        old_target = [("matches", "0022_rematch_request")]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        user_model = old_apps.get_model("auth", "User")
        match_model = old_apps.get_model("matches", "Match")
        player_model = old_apps.get_model("matches", "MatchPlayer")
        skill_model = old_apps.get_model("matches", "Skill")
        match_skill_model = old_apps.get_model("matches", "MatchSkill")
        skill_use_model = old_apps.get_model("matches", "SkillUse")
        effect_model = old_apps.get_model("matches", "SkillEffect")
        host = user_model.objects.create(username="legacy-shield-host")
        opponent = user_model.objects.create(username="legacy-shield-opponent")
        match = match_model.objects.create(
            room_code="OLDGRD",
            host_id=host.pk,
            status="PLAYING",
            started_at=timezone.now(),
        )
        legacy_snapshot = deepcopy(match.rules_snapshot)
        legacy_snapshot["required_skill_codes"] = [
            code for code in legacy_snapshot["required_skill_codes"] if code != SHIELD
        ]
        match.ruleset_version = "v3.1"
        match.rules_snapshot = legacy_snapshot
        match.save(update_fields=["ruleset_version", "rules_snapshot"])
        host_player = player_model.objects.create(
            match_id=match.pk,
            user_id=host.pk,
            slot=1,
            is_host=True,
            is_active=True,
        )
        opponent_player = player_model.objects.create(
            match_id=match.pk,
            user_id=opponent.pk,
            slot=2,
            is_active=True,
        )
        skill, _ = skill_model.objects.get_or_create(
            code=MIRROR_CODE,
            defaults={
                "name": "Đảo chiều code",
                "description": "Legacy Mirror",
                "energy_cost": 1,
                "duration_seconds": 35,
                "is_active": True,
            },
        )
        match_skill = match_skill_model.objects.create(
            match_id=match.pk,
            skill_id=skill.pk,
            code_snapshot=MIRROR_CODE,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            energy_cost_snapshot=skill.energy_cost,
            duration_seconds_snapshot=skill.duration_seconds,
        )
        skill_use = skill_use_model.objects.create(
            match_id=match.pk,
            source_player_id=host_player.pk,
            target_player_id=opponent_player.pk,
            match_skill_id=match_skill.pk,
            energy_spent=1,
            idempotency_key="legacy-effect",
        )
        effect_model.objects.create(
            skill_use_id=skill_use.pk,
            started_at=match.started_at,
            expires_at=match.started_at + timedelta(seconds=35),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        apps = executor.loader.project_state(leaves).apps
        migrated_match = apps.get_model("matches", "Match").objects.get(pk=match.pk)
        migrated_skill = apps.get_model("matches", "MatchSkill").objects.get(
            pk=match_skill.pk
        )
        migrated_effect = apps.get_model("matches", "SkillEffect").objects.get(
            skill_use_id=skill_use.pk
        )

        self.assertEqual(migrated_match.ruleset_version, "v3.1")
        self.assertNotIn(SHIELD, migrated_match.rules_snapshot["required_skill_codes"])
        self.assertEqual(migrated_skill.policy_snapshot["handler"], "TIMED")
        self.assertIsNone(migrated_effect.consumed_at)
        self.assertTrue(
            apps.get_model("matches", "Skill").objects.filter(code=SHIELD).exists()
        )
        self.assertFalse(
            apps.get_model("matches", "MatchSkill")
            .objects.filter(
                match_id=match.pk,
                code_snapshot=SHIELD,
            )
            .exists()
        )


class ShieldConcurrencyTests(ShieldFixtureMixin, TransactionTestCase):
    def setUp(self):
        self.create_shield_fixture(room_code="RACEGD")

    def test_two_attacks_consume_shield_only_once(self):
        now = timezone.now()
        self.activate_shield(now=now)
        self.grant(self.opponent_player, MIRROR_CODE, energy=3)
        self.grant(self.opponent_player, BLUR_STATEMENT, energy=3)
        barrier = Barrier(2)

        def attack(code):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return SkillService().use(
                    user=self.opponent,
                    match_id=self.match.pk,
                    skill_code=code,
                    target_player_id=self.host_player.pk,
                    idempotency_key=f"race-{code}",
                    now=now + timedelta(seconds=1),
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attack, [MIRROR_CODE, BLUR_STATEMENT]))

        outcomes = [result.skill_use.outcome_snapshot.get("kind") for result in results]
        self.assertEqual(outcomes.count("BLOCKED_BY_SHIELD"), 1)
        self.assertEqual(outcomes.count(None), 1)
        self.assertEqual(
            SkillEffect.objects.filter(consumed_at__isnull=False).count(),
            1,
        )
        self.assertEqual(
            SkillEffect.objects.filter(
                skill_use__match_skill__code_snapshot__in=(
                    MIRROR_CODE,
                    BLUR_STATEMENT,
                )
            ).count(),
            1,
        )
