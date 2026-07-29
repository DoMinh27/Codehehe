from copy import deepcopy

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.utils import override_settings

from matches.rules import (
    CURRENT_RULESET_VERSION,
    MatchRules,
    RulesetConfigurationError,
    current_match_rules,
    rules_for_match,
)
from matches.services.room import CreateRoomService
from matches.skills.definitions import TYPING_PROMPTS


User = get_user_model()


class MatchRulesTests(SimpleTestCase):
    def test_current_rules_round_trip_without_changing_typing_prompts(self):
        rules = current_match_rules()

        restored = MatchRules.from_snapshot(
            version=rules.version,
            snapshot=rules.to_snapshot(),
        )

        self.assertEqual(restored, rules)
        self.assertEqual(restored.typing_prompts, TYPING_PROMPTS)

    def test_invalid_snapshot_is_rejected(self):
        snapshot = current_match_rules().to_snapshot()
        snapshot["match_duration_seconds"] = 0

        with self.assertRaises(RulesetConfigurationError):
            MatchRules.from_snapshot(
                version=CURRENT_RULESET_VERSION,
                snapshot=snapshot,
            )

    @override_settings(MATCH_DURATION_SECONDS=0)
    def test_invalid_duration_setting_is_rejected(self):
        with self.assertRaises(RulesetConfigurationError):
            current_match_rules()


class MatchRulesPersistenceTests(TestCase):
    @override_settings(MATCH_DURATION_SECONDS=420)
    def test_room_snapshots_rules_and_later_settings_do_not_change_them(self):
        user = User.objects.create(username="rules-host")
        match = CreateRoomService(
            code_generator=lambda: "RULES1",
        ).create(user=user)

        self.assertEqual(match.duration_seconds, 420)
        self.assertEqual(match.ruleset_version, CURRENT_RULESET_VERSION)
        self.assertEqual(
            match.rules_snapshot["match_duration_seconds"],
            420,
        )

        with self.settings(MATCH_DURATION_SECONDS=600):
            restored = rules_for_match(match)

        self.assertEqual(restored.match_duration_seconds, 420)
        self.assertEqual(restored.typing_prompts, TYPING_PROMPTS)

    def test_corrupt_persisted_snapshot_is_rejected(self):
        user = User.objects.create(username="invalid-rules-host")
        match = CreateRoomService(
            code_generator=lambda: "RULES2",
        ).create(user=user)
        snapshot = deepcopy(match.rules_snapshot)
        del snapshot["energy"]
        match.rules_snapshot = snapshot

        with self.assertRaises(RulesetConfigurationError):
            rules_for_match(match)


class MatchRulesMigrationTests(TransactionTestCase):
    migrate_from = [("matches", "0012_typing_challenge")]
    migrate_to = [("matches", "0013_match_ruleset_snapshot")]

    def test_existing_match_duration_is_preserved_in_snapshot(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        user_model = old_apps.get_model("auth", "User")
        match_model = old_apps.get_model("matches", "Match")
        user = user_model.objects.create(username="migration-host")
        old_match = match_model.objects.create(
            room_code="MIGR13",
            host_id=user.pk,
            duration_seconds=900,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        migrated_match = new_apps.get_model("matches", "Match").objects.get(
            pk=old_match.pk
        )

        self.assertEqual(migrated_match.duration_seconds, 900)
        self.assertEqual(
            migrated_match.rules_snapshot["match_duration_seconds"],
            900,
        )
        self.assertEqual(
            migrated_match.ruleset_version,
            CURRENT_RULESET_VERSION,
        )
