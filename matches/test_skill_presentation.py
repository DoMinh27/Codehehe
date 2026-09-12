from datetime import timedelta
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from matches.services.match_state import MatchStateService
from matches.skills.definitions import (
    BLUR_STATEMENT,
    MIRROR_CODE,
    PURIFY,
    SHIELD,
    STEAL,
    TIME_DRAIN_60,
)
from matches.skills.presentation import combat_feedback_for
from matches.skills.service import SkillService
from matches.test_skill_engine_shield import ShieldFixtureMixin


class CombatFeedbackProjectionTests(SimpleTestCase):
    def feedback(self, *, code, viewer_id, outcome=None):
        skill_use = SimpleNamespace(
            pk=17,
            source_player_id=1,
            target_player_id=2,
            used_at=timezone.now(),
            outcome_snapshot=outcome or {},
            match_skill=SimpleNamespace(
                code_snapshot=code,
                name_snapshot="Legacy name",
            ),
        )
        return combat_feedback_for(
            skill_use=skill_use,
            viewer_player=SimpleNamespace(pk=viewer_id),
            time_drain_seconds=60,
        )

    def test_timed_attack_has_different_actor_and_target_feedback(self):
        self.assertEqual(
            self.feedback(code=MIRROR_CODE, viewer_id=1)["text"],
            "Đã dùng Đảo chiều code",
        )
        target_feedback = self.feedback(code=MIRROR_CODE, viewer_id=2)
        self.assertEqual(target_feedback["text"], "Bạn đang bị Đảo chiều code")
        self.assertEqual(target_feedback["cue"], "MIRROR_HIT")

    def test_time_drain_and_steal_report_only_their_safe_outcomes(self):
        time_feedback = self.feedback(code=TIME_DRAIN_60, viewer_id=2)
        steal_feedback = self.feedback(
            code=STEAL,
            viewer_id=2,
            outcome={
                "kind": "STOLEN_SKILL",
                "skill_code": BLUR_STATEMENT,
                "skill_name": "Làm mờ đề",
            },
        )

        self.assertEqual(time_feedback["text"], "Bạn bị trừ 60 giây")
        self.assertEqual(steal_feedback["text"], "Bạn mất 1 lượt Che mờ đề")

    def test_blocked_attack_is_tailored_and_outsiders_receive_nothing(self):
        outcome = {
            "kind": "BLOCKED_BY_SHIELD",
            "skill_code": "SHIELD",
            "skill_name": "Shield",
        }

        self.assertEqual(
            self.feedback(code=MIRROR_CODE, viewer_id=1, outcome=outcome)["text"],
            "Đòn đã bị chặn",
        )
        self.assertEqual(
            self.feedback(code=MIRROR_CODE, viewer_id=2, outcome=outcome)["text"],
            "Khiên đã chặn Đảo chiều code",
        )
        self.assertIsNone(
            self.feedback(code=MIRROR_CODE, viewer_id=3, outcome=outcome)
        )


class SkillPresentationTests(ShieldFixtureMixin, TestCase):
    def setUp(self):
        self.create_shield_fixture(room_code="PRES01")

    def test_state_exposes_structured_vietnamese_presentation(self):
        payload = MatchStateService().get(user=self.host, match_id=self.match.pk)
        skills = {skill["code"]: skill for skill in payload["my_skills"]}

        self.assertEqual(skills[MIRROR_CODE]["name"], "Đảo chiều code")
        self.assertEqual(
            skills[MIRROR_CODE]["description"],
            "Đảo chiều vùng soạn thảo của đối thủ",
        )
        self.assertEqual(skills[MIRROR_CODE]["target_label"], "Đối thủ")
        self.assertEqual(skills[MIRROR_CODE]["effect_label"], "35 giây")
        self.assertEqual(skills[PURIFY]["special_rule"], "Không hoàn lại thời gian đã mất")
        self.assertEqual(skills[SHIELD]["name"], "Khiên")
        self.assertEqual(skills[SHIELD]["effect_label"], "1 đòn hoặc 45 giây")
        self.assertIsNone(skills[SHIELD]["special_rule"])

    def test_shield_activation_is_private_until_it_blocks_an_attack(self):
        now = timezone.now()
        self.activate_shield(now=now)

        owner_state = MatchStateService().get(
            user=self.host,
            match_id=self.match.pk,
            now=now + timedelta(seconds=1),
        )
        opponent_state = MatchStateService().get(
            user=self.opponent,
            match_id=self.match.pk,
            now=now + timedelta(seconds=1),
        )

        shield_feedback = owner_state["combat_notifications"][-1]
        self.assertEqual(shield_feedback["text"], "Khiên đã sẵn sàng")
        self.assertEqual(
            set(shield_feedback),
            {"id", "text", "cue", "tone", "created_at"},
        )
        self.assertEqual(opponent_state["combat_notifications"], [])
        self.assertEqual(owner_state["active_effects"][0]["name"], "Khiên")
        self.assertNotIn("source_player_id", owner_state["active_effects"][0])
        self.assertNotIn("source_username", owner_state["active_effects"][0])
        self.assertEqual(opponent_state["active_effects"], [])
        self.assertNotIn("recent_skill_uses", owner_state)

    def test_purify_is_visible_only_to_its_user(self):
        now = timezone.now()
        self.grant(self.opponent_player, MIRROR_CODE, energy=3)
        SkillService().use(
            user=self.opponent,
            match_id=self.match.pk,
            skill_code=MIRROR_CODE,
            target_player_id=self.host_player.pk,
            idempotency_key="mirror-host",
            now=now,
        )
        self.grant(self.host_player, PURIFY, energy=3)
        purified = SkillService().use(
            user=self.host,
            match_id=self.match.pk,
            skill_code=PURIFY,
            target_player_id=self.host_player.pk,
            idempotency_key="purify-host",
            now=now + timedelta(seconds=1),
        )

        owner_state = MatchStateService().get(user=self.host, match_id=self.match.pk)
        opponent_state = MatchStateService().get(
            user=self.opponent,
            match_id=self.match.pk,
        )
        owner_feedback = next(
            item
            for item in owner_state["combat_notifications"]
            if item["id"] == purified.skill_use.pk
        )

        self.assertEqual(owner_feedback["text"], "Đã hóa giải Đảo chiều code")
        self.assertFalse(
            any(
                item["id"] == purified.skill_use.pk
                for item in opponent_state["combat_notifications"]
            )
        )


class SkillPresentationMigrationTests(TransactionTestCase):
    def test_forward_migration_updates_skill_and_match_snapshots(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        old_target = [("matches", "0026_update_skill_microcopy")]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        user_model = old_apps.get_model("auth", "User")
        match_model = old_apps.get_model("matches", "Match")
        skill_model = old_apps.get_model("matches", "Skill")
        match_skill_model = old_apps.get_model("matches", "MatchSkill")

        user = user_model.objects.create(username="presentation-migration")
        match = match_model.objects.create(room_code="MIG027", host_id=user.pk)
        skill, _ = skill_model.objects.update_or_create(
            code="SHIELD",
            defaults={
                "name": "Shield",
                "description": (
                    "Chặn skill tấn công hợp lệ tiếp theo trong tối đa 45 giây"
                ),
                "energy_cost": 1,
                "duration_seconds": 45,
                "is_active": True,
            },
        )
        match_skill_model.objects.create(
            match_id=match.pk,
            skill_id=skill.pk,
            code_snapshot="SHIELD",
            name_snapshot="Shield",
            description_snapshot=skill.description,
            energy_cost_snapshot=1,
            duration_seconds_snapshot=45,
            policy_snapshot={},
        )

        new_target = [("matches", "0027_update_skill_presentation")]
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        migrated_skill = new_apps.get_model("matches", "Skill").objects.get(
            code="SHIELD"
        )
        migrated_snapshot = new_apps.get_model("matches", "MatchSkill").objects.get(
            match_id=match.pk,
            code_snapshot="SHIELD",
        )

        self.assertEqual(migrated_skill.name, "Khiên")
        self.assertEqual(migrated_snapshot.name_snapshot, "Khiên")
        self.assertEqual(
            migrated_snapshot.description_snapshot,
            "Chặn kỹ năng tấn công tiếp theo",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        restored_apps = executor.loader.project_state(old_target).apps
        restored_skill = restored_apps.get_model("matches", "Skill").objects.get(
            code="SHIELD"
        )
        restored_snapshot = restored_apps.get_model(
            "matches", "MatchSkill"
        ).objects.get(match_id=match.pk, code_snapshot="SHIELD")

        self.assertEqual(restored_skill.name, "Shield")
        self.assertEqual(restored_snapshot.name_snapshot, "Shield")
        self.assertEqual(
            restored_snapshot.description_snapshot,
            "Chặn skill tấn công hợp lệ tiếp theo trong tối đa 45 giây",
        )
