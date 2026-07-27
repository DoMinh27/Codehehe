import json
import os
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Verdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    JUDGE_ERROR = "JUDGE_ERROR"


class Judge0ConfigurationError(RuntimeError):
    """Raised when the external Judge0 endpoint has not been configured."""


class Judge0UnavailableError(RuntimeError):
    """Raised when Judge0 cannot be reached or returns an invalid response."""


@dataclass(frozen=True)
class JudgeTestCase:
    """A test case passed from the backend to a code judge."""

    input_data: str
    expected_output: str


@dataclass(frozen=True)
class JudgeResult:
    verdict: Verdict
    passed_test_cases: int = 0
    total_test_cases: int = 0
    stdout: str = ""
    stderr: str = ""
    message: str = ""

    @property
    def is_accepted(self) -> bool:
        return self.verdict is Verdict.ACCEPTED


class JudgeService(Protocol):
    """Contract shared by the fake judge and the future Judge0 adapter."""

    def judge(
        self,
        *,
        source_code: str,
        test_cases: Sequence[JudgeTestCase],
    ) -> JudgeResult:
        """Run source code against backend-only test cases."""


@dataclass
class FakeJudgeService:
    """Deterministic judge used in development and service tests.

    It deliberately does not execute source code.  A later Judge0Service will
    implement the same JudgeService contract and run code in an external
    sandbox.
    """

    result: JudgeResult = field(
        default_factory=lambda: JudgeResult(verdict=Verdict.ACCEPTED)
    )
    calls: list[tuple[str, tuple[JudgeTestCase, ...]]] = field(default_factory=list)

    def judge(
        self,
        *,
        source_code: str,
        test_cases: Sequence[JudgeTestCase],
    ) -> JudgeResult:
        if not source_code.strip():
            raise ValueError("source_code must not be empty")

        recorded_test_cases = tuple(test_cases)
        self.calls.append((source_code, recorded_test_cases))
        total_test_cases = len(recorded_test_cases)
        passed_test_cases = (
            total_test_cases if self.result.is_accepted else self.result.passed_test_cases
        )

        return replace(
            self.result,
            passed_test_cases=passed_test_cases,
            total_test_cases=total_test_cases,
        )


@dataclass
class Judge0Service:
    """Judge Python code through a Judge0-compatible external endpoint.

    Each test is submitted separately so this service can report how many tests
    passed while keeping every expected output on the backend.
    """

    base_url: str
    api_key: str = ""
    language_id: int = 71  # Python (3.8.1) in Judge0 CE.
    timeout_seconds: int = 15

    @classmethod
    def from_environment(cls) -> "Judge0Service":
        base_url = os.getenv("JUDGE0_BASE_URL", "").strip()
        if not base_url:
            raise Judge0ConfigurationError("JUDGE0_BASE_URL is not configured")

        return cls(
            base_url=base_url,
            api_key=os.getenv("JUDGE0_API_KEY", "").strip(),
        )

    def judge(
        self,
        *,
        source_code: str,
        test_cases: Sequence[JudgeTestCase],
    ) -> JudgeResult:
        if not source_code.strip():
            raise ValueError("source_code must not be empty")

        test_cases = tuple(test_cases)
        for passed_count, test_case in enumerate(test_cases):
            response = self._submit(source_code, test_case)
            verdict = self._verdict_from_response(response)
            if verdict is not Verdict.ACCEPTED:
                return JudgeResult(
                    verdict=verdict,
                    passed_test_cases=passed_count,
                    total_test_cases=len(test_cases),
                    stdout=str(response.get("stdout") or ""),
                    stderr=str(response.get("stderr") or ""),
                    message=str(response.get("message") or ""),
                )

        return JudgeResult(
            verdict=Verdict.ACCEPTED,
            passed_test_cases=len(test_cases),
            total_test_cases=len(test_cases),
        )

    def _submit(self, source_code: str, test_case: JudgeTestCase) -> dict[str, Any]:
        payload = json.dumps(
            {
                "source_code": source_code,
                "language_id": self.language_id,
                "stdin": test_case.input_data,
                "expected_output": test_case.expected_output,
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key

        request = Request(
            f"{self.base_url.rstrip('/')}/submissions?base64_encoded=false&wait=true",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                data = json.loads(response.read().decode())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise Judge0UnavailableError("Judge0 request failed") from error

        if not isinstance(data, dict):
            raise Judge0UnavailableError("Judge0 returned an invalid response")
        return data

    @staticmethod
    def _verdict_from_response(response: dict[str, Any]) -> Verdict:
        status = response.get("status")
        status_id = status.get("id") if isinstance(status, dict) else None
        mapping = {
            3: Verdict.ACCEPTED,
            4: Verdict.WRONG_ANSWER,
            5: Verdict.TIME_LIMIT_EXCEEDED,
            6: Verdict.COMPILATION_ERROR,
            7: Verdict.RUNTIME_ERROR,
            8: Verdict.RUNTIME_ERROR,
            9: Verdict.RUNTIME_ERROR,
            10: Verdict.RUNTIME_ERROR,
            11: Verdict.RUNTIME_ERROR,
            12: Verdict.RUNTIME_ERROR,
        }
        return mapping.get(status_id, Verdict.JUDGE_ERROR)
