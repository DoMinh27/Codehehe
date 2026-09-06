import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from matches.services.run import (
    CodeRunConflictError,
    CodeRunNotFoundError,
    CodeRunPermissionError,
    CodeRunUnavailableError,
    InvalidCodeRunError,
)
from matches.services.submission import (
    InvalidSubmissionError,
    SubmissionConflictError,
    SubmissionNotFoundError,
    SubmissionPermissionError,
)
from matches.skills.service import (
    InvalidSkillUseError,
    SkillUseConflictError,
    SkillUseNotFoundError,
    SkillUsePermissionError,
)
from matches.skills.typing import (
    InvalidTypingChallengeError,
    TypingChallengeConflictError,
    TypingChallengeNotFoundError,
    TypingChallengePermissionError,
)
from matches.views.api import ApiPayloadError, api_error, parse_json_object
from matches.views.skills import complete_typing_challenge, use_skill
from matches.views.submissions import run_code, submit_submission


class ApiHelperTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_parse_json_object_accepts_only_an_object(self):
        request = self.factory.post(
            "/",
            data=json.dumps({"source_code": "print(1)"}),
            content_type="application/json",
        )

        self.assertEqual(
            parse_json_object(request),
            {"source_code": "print(1)"},
        )

        for body, expected_code in (
            ("{", "INVALID_JSON"),
            ("[]", "INVALID_BODY"),
        ):
            with self.subTest(body=body):
                invalid_request = self.factory.post(
                    "/",
                    data=body,
                    content_type="application/json",
                )
                with self.assertRaises(ApiPayloadError) as context:
                    parse_json_object(invalid_request)
                self.assertEqual(context.exception.code, expected_code)

    def test_api_error_has_exact_stable_contract(self):
        response = api_error(
            code="MATCH_NOT_PLAYING",
            message="Trận đấu không ở trạng thái đang chơi.",
            status=409,
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            json.loads(response.content),
            {
                "code": "MATCH_NOT_PLAYING",
                "message": "Trận đấu không ở trạng thái đang chơi",
            },
        )


class EndpointApiErrorMappingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, pk=1)

    def post(self, body=None):
        request = self.factory.post(
            "/",
            data=json.dumps(body or {}),
            content_type="application/json",
        )
        request.user = self.user
        return request

    def assert_api_error(self, response, *, status, code):
        self.assertEqual(response.status_code, status)
        payload = json.loads(response.content)
        self.assertEqual(set(payload), {"code", "message"})
        self.assertEqual(payload["code"], code)

    def test_run_error_codes_are_stable(self):
        cases = (
            (InvalidCodeRunError("invalid"), 400, "INVALID_CODE_RUN"),
            (CodeRunPermissionError("forbidden"), 403, "CODE_RUN_FORBIDDEN"),
            (CodeRunNotFoundError("missing"), 404, "MATCH_PROBLEM_NOT_FOUND"),
            (CodeRunConflictError("conflict"), 409, "CODE_RUN_CONFLICT"),
            (CodeRunUnavailableError("down"), 503, "CODE_RUN_UNAVAILABLE"),
        )
        for error, status, code in cases:
            with (
                self.subTest(code=code),
                patch(
                    "matches.views.submissions.is_rate_limited",
                    return_value=False,
                ),
                patch(
                    "matches.views.submissions.Judge0Service.from_environment",
                    return_value=Mock(),
                ),
                patch(
                    "matches.views.submissions.CodeRunService.run",
                    side_effect=error,
                ),
            ):
                response = run_code(self.post(), 1, 2)
                self.assert_api_error(response, status=status, code=code)

    def test_submission_error_codes_are_stable(self):
        cases = (
            (InvalidSubmissionError("invalid"), 400, "INVALID_SUBMISSION"),
            (
                SubmissionPermissionError("forbidden"),
                403,
                "SUBMISSION_FORBIDDEN",
            ),
            (
                SubmissionNotFoundError("missing"),
                404,
                "MATCH_PROBLEM_NOT_FOUND",
            ),
            (
                SubmissionConflictError("conflict"),
                409,
                "SUBMISSION_CONFLICT",
            ),
        )
        for error, status, code in cases:
            with (
                self.subTest(code=code),
                patch(
                    "matches.views.submissions.is_rate_limited",
                    return_value=False,
                ),
                patch(
                    "matches.views.submissions.Judge0Service.from_environment",
                    return_value=Mock(),
                ),
                patch(
                    "matches.views.submissions.SubmissionService.submit",
                    side_effect=error,
                ),
            ):
                response = submit_submission(self.post(), 1, 2)
                self.assert_api_error(response, status=status, code=code)

    def test_skill_error_codes_are_stable(self):
        cases = (
            (InvalidSkillUseError("invalid"), 400, "INVALID_SKILL_USE"),
            (
                SkillUsePermissionError("forbidden"),
                403,
                "SKILL_USE_FORBIDDEN",
            ),
            (SkillUseNotFoundError("missing"), 404, "SKILL_NOT_FOUND"),
            (SkillUseConflictError("conflict"), 409, "SKILL_USE_CONFLICT"),
        )
        for error, status, code in cases:
            with (
                self.subTest(code=code),
                patch(
                    "matches.views.skills.SkillService.use",
                    side_effect=error,
                ),
            ):
                response = use_skill(self.post(), 1, "BLUR")
                self.assert_api_error(response, status=status, code=code)

    def test_typing_error_codes_are_stable(self):
        cases = (
            (
                InvalidTypingChallengeError("invalid"),
                400,
                "INVALID_TYPING_CHALLENGE",
            ),
            (
                TypingChallengePermissionError("forbidden"),
                403,
                "TYPING_CHALLENGE_FORBIDDEN",
            ),
            (
                TypingChallengeNotFoundError("missing"),
                404,
                "TYPING_CHALLENGE_NOT_FOUND",
            ),
            (
                TypingChallengeConflictError("conflict"),
                409,
                "TYPING_CHALLENGE_CONFLICT",
            ),
        )
        for error, status, code in cases:
            with (
                self.subTest(code=code),
                patch(
                    "matches.views.skills.TypingChallengeService.complete",
                    side_effect=error,
                ),
            ):
                response = complete_typing_challenge(self.post(), 1, 2)
                self.assert_api_error(response, status=status, code=code)
