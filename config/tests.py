from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from problems.services.judge import Judge0ConfigurationError


class HealthCheckTests(SimpleTestCase):
    def test_health_returns_ok(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class ReadinessCheckTests(SimpleTestCase):
    databases = {"default"}

    def test_readiness_checks_database(self):
        response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    @patch("config.views.connection.cursor")
    def test_readiness_returns_503_when_database_is_unavailable(self, cursor):
        cursor.side_effect = DatabaseError("private database detail")

        response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "dependency": "database"},
        )
        self.assertNotContains(
            response,
            "private database detail",
            status_code=503,
        )

    @override_settings(READINESS_CHECK_JUDGE0=True)
    @patch("config.views.Judge0Service.from_environment")
    def test_readiness_returns_503_when_judge_is_unavailable(self, factory):
        factory.side_effect = Judge0ConfigurationError("private judge detail")

        response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "dependency": "judge0"},
        )
        self.assertNotContains(response, "private judge detail", status_code=503)
